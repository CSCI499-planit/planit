"""
Stage 4 — Itinerary Optimization (OR-Tools VRP)

Uses Google OR-Tools to solve a Vehicle Routing Problem with Time Windows (VRPTW).
One "vehicle" per trip day. Falls back to greedy nearest-neighbor if the solver
returns no solution (e.g. over-constrained by tight time windows).

Constraints:
  - max_places_per_day   (capacity per vehicle, derived from itinerary_pace)
  - trip_days            (number of vehicles)
  - travel_mode          (speed used for travel time matrix)
  - time windows         (parsed from place hours; defaults to 9 AM–10 PM)

Output shape (one entry per day):
  {
    "day":   1,
    "date":  "2024-06-15",   # None if start_date not provided
    "stops": [
      {
        "place":          PlaceRecord,
        "arrival_time":   "10:00",
        "departure_time": "11:30",
        "travel_to_next": {"mode": "walk", "minutes": 12, "distance_m": 950}
      }
    ]
  }

TODO: replace default time windows with structured hours data once
      PlaceRecord.hours is parsed into open/close times.
"""
from __future__ import annotations

import logging
import math
import re
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

if TYPE_CHECKING:
    from ml.data.preprocess import PlaceRecord

from ml.models.user_profiler import PACE_TO_MAX_PLACES

logger = logging.getLogger(__name__)

# Urban travel speed estimates (km/h)
_TRAVEL_SPEED_KMH: dict[str, float] = {
    "walk":    5.0,
    "bike":   15.0,
    "transit": 25.0,
    "drive":   30.0,
}

# Typical dwell time per tag (minutes) — first matching tag wins
_TAG_DWELL_MINUTES: dict[str, int] = {
    "quick_visit":     30,
    "food_and_drink":  60,
    "cultural":        90,
    "historical":      90,
    "outdoor":         60,
    "scenic":          45,
    "shopping":        60,
    "wellness":        60,
    "nightlife":       90,
    "adventurous":     90,
    "family_friendly": 90,
    "upscale":         75,
    "romantic":        60,
    "pet_friendly":    45,
    "budget_friendly": 30,
}
_DEFAULT_DWELL_MINUTES: int = 60

_DAY_START_MINUTES: int = 9 * 60    # 9:00 AM in minutes from midnight
_DAY_END_MINUTES:   int = 22 * 60   # 10:00 PM

_VRP_SOLVER_TIME_LIMIT_SECONDS: int = 10


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _travel_minutes(lat1: float, lon1: float, lat2: float, lon2: float, mode: str) -> int:
    dist_km = _haversine_km(lat1, lon1, lat2, lon2)
    speed   = _TRAVEL_SPEED_KMH.get(mode, 25.0)
    return max(1, round((dist_km / speed) * 60))


def _dwell_minutes(place: PlaceRecord) -> int:
    for tag in (place.get("tags") or []):
        if tag in _TAG_DWELL_MINUTES:
            return _TAG_DWELL_MINUTES[tag]
    return _DEFAULT_DWELL_MINUTES


def _parse_time_window(hours: str | None) -> tuple[int, int]:
    """
    Best-effort parse of a raw hours string into (open, close) minutes from midnight.
    Returns the default window (9 AM–10 PM) if parsing fails.
    Examples handled: "09:00-21:00", "9am-9pm", "Mon-Sun 10:00-22:00"
    """
    if not hours:
        return (_DAY_START_MINUTES, _DAY_END_MINUTES)

    # look for HH:MM-HH:MM or H:MM-H:MM
    m = re.search(r"(\d{1,2}):(\d{2})\s*[-–]\s*(\d{1,2}):(\d{2})", hours)
    if m:
        open_min  = int(m.group(1)) * 60 + int(m.group(2))
        close_min = int(m.group(3)) * 60 + int(m.group(4))
        if open_min < close_min:
            return (open_min, close_min)

    # look for 9am-9pm style
    m = re.search(r"(\d{1,2})(am|pm)\s*[-–]\s*(\d{1,2})(am|pm)", hours, re.IGNORECASE)
    if m:
        def to_24h(h: int, period: str) -> int:
            if period.lower() == "pm" and h != 12:
                return h + 12
            if period.lower() == "am" and h == 12:
                return 0
            return h
        open_min  = to_24h(int(m.group(1)), m.group(2)) * 60
        close_min = to_24h(int(m.group(3)), m.group(4)) * 60
        if open_min < close_min:
            return (open_min, close_min)

    return (_DAY_START_MINUTES, _DAY_END_MINUTES)


def _minutes_to_time(minutes: int) -> str:
    h = (minutes // 60) % 24
    m = minutes % 60
    return f"{h:02d}:{m:02d}"


# ---------------------------------------------------------------------------
# Greedy fallback (used when OR-Tools returns no solution)
# ---------------------------------------------------------------------------

def _nearest_neighbor_order(places: list[PlaceRecord]) -> list[PlaceRecord]:
    if len(places) <= 1:
        return list(places)
    remaining = list(places)
    ordered   = [remaining.pop(0)]
    while remaining:
        last     = ordered[-1]
        best_idx = min(
            range(len(remaining)),
            key=lambda i: _haversine_km(
                last["latitude"],         last["longitude"],
                remaining[i]["latitude"], remaining[i]["longitude"],
            ),
        )
        ordered.append(remaining.pop(best_idx))
    return ordered


def _build_day(
    places:    list[PlaceRecord],
    day_idx:   int,
    mode:      str,
    start_date: str | None,
    arrival_times: list[int] | None = None,
) -> dict:
    """Assemble a day dict from an ordered list of places and optional arrival times (minutes from midnight)."""
    stops: list[dict] = []
    for i, place in enumerate(places):
        if arrival_times:
            arr_min = arrival_times[i]
        else:
            # greedy: accumulate from day start
            arr_min = _DAY_START_MINUTES
            if i > 0:
                prev      = places[i - 1]
                prev_arr  = arrival_times[i - 1] if arrival_times else _DAY_START_MINUTES
                prev_dep  = prev_arr + _dwell_minutes(prev)
                t_min     = _travel_minutes(
                    prev["latitude"], prev["longitude"],
                    place["latitude"], place["longitude"],
                    mode,
                )
                arr_min = prev_dep + t_min

        dwell   = _dwell_minutes(place)
        dep_min = arr_min + dwell

        travel_to_next = None
        if i < len(places) - 1:
            nxt    = places[i + 1]
            t_min  = _travel_minutes(
                place["latitude"], place["longitude"],
                nxt["latitude"],   nxt["longitude"],
                mode,
            )
            dist_m = round(_haversine_km(
                place["latitude"], place["longitude"],
                nxt["latitude"],   nxt["longitude"],
            ) * 1000)
            travel_to_next = {"mode": mode, "minutes": t_min, "distance_m": dist_m}

        stops.append({
            "place":          place,
            "arrival_time":   _minutes_to_time(arr_min),
            "departure_time": _minutes_to_time(dep_min),
            "travel_to_next": travel_to_next,
        })

    date_str: str | None = None
    if start_date:
        try:
            base     = datetime.strptime(start_date, "%Y-%m-%d")
            date_str = (base + timedelta(days=day_idx)).strftime("%Y-%m-%d")
        except ValueError:
            pass

    return {"day": day_idx + 1, "date": date_str, "stops": stops}


def _greedy_fallback(candidates: list[PlaceRecord], trip_context: dict) -> list[dict]:
    pace        = trip_context.get("itinerary_pace", "balanced")
    max_per_day = PACE_TO_MAX_PLACES.get(pace, 4)
    modes       = trip_context.get("travel_mode") or ["transit"]
    mode        = modes[0] if isinstance(modes, list) else modes
    trip_days   = int(trip_context.get("trip_days", 1))
    start_date  = trip_context.get("start_date")

    days_out = []
    for day_idx in range(trip_days):
        day_places = candidates[day_idx * max_per_day : (day_idx + 1) * max_per_day]
        if not day_places:
            break
        ordered = _nearest_neighbor_order(day_places)
        days_out.append(_build_day(ordered, day_idx, mode, start_date))
    return days_out


# ---------------------------------------------------------------------------
# RouteOptimizer
# ---------------------------------------------------------------------------

class RouteOptimizer:

    def optimize(
        self,
        ranked_places: list[PlaceRecord],
        trip_context:  dict,
    ) -> list[dict]:
        pace        = trip_context.get("itinerary_pace", "balanced")
        max_per_day = PACE_TO_MAX_PLACES.get(pace, 4)
        modes       = trip_context.get("travel_mode") or ["transit"]
        mode        = modes[0] if isinstance(modes, list) else modes
        trip_days   = int(trip_context.get("trip_days", 1))
        start_date  = trip_context.get("start_date")

        candidates = ranked_places[: max_per_day * trip_days]
        if not candidates:
            return []
        if len(candidates) == 1:
            return [_build_day(candidates, 0, mode, start_date)]

        # --- Build OR-Tools data model ---
        # Node 0 = virtual depot (centroid of all candidates)
        # Nodes 1..N = candidate places
        all_lats  = [p.get("latitude", 0.0)  for p in candidates]
        all_lons  = [p.get("longitude", 0.0) for p in candidates]
        depot_lat = sum(all_lats) / len(all_lats)
        depot_lon = sum(all_lons) / len(all_lons)

        locations = [(depot_lat, depot_lon)] + [(p.get("latitude", 0.0), p.get("longitude", 0.0)) for p in candidates]  # type: ignore[typeddict-item]
        n         = len(locations)
        speed     = _TRAVEL_SPEED_KMH.get(mode, 25.0)

        # Integer travel time matrix (minutes)
        time_matrix: list[list[int]] = []
        for i in range(n):
            row = []
            for j in range(n):
                if i == j:
                    row.append(0)
                else:
                    dist_km = _haversine_km(locations[i][0], locations[i][1],
                                            locations[j][0], locations[j][1])
                    row.append(max(1, round((dist_km / speed) * 60)))
            time_matrix.append(row)

        # Service (dwell) times — 0 for depot
        service_times = [0] + [_dwell_minutes(p) for p in candidates]

        # Time windows (minutes from midnight); depot fixed at day start
        time_windows = [(_DAY_START_MINUTES, _DAY_START_MINUTES)]  # depot
        for p in candidates:
            time_windows.append(_parse_time_window(p.get("hours")))

        # --- OR-Tools setup ---
        manager = pywrapcp.RoutingIndexManager(n, trip_days, 0)
        routing = pywrapcp.RoutingModel(manager)

        def time_callback(from_index: int, to_index: int) -> int:
            from_node = manager.IndexToNode(from_index)
            to_node   = manager.IndexToNode(to_index)
            return time_matrix[from_node][to_node] + service_times[from_node]

        transit_idx = routing.RegisterTransitCallback(time_callback)
        routing.SetArcCostEvaluatorOfAllVehicles(transit_idx)

        # Time dimension — absolute minutes from midnight
        routing.AddDimension(
            transit_idx,
            60,     # max waiting slack (1 hour)
            1440,   # max time per vehicle (24 h ceiling)
            False,  # don't force start cumul to zero — we use absolute times
            "Time",
        )
        time_dim = routing.GetDimensionOrDie("Time")

        for node_idx, (tw_open, tw_close) in enumerate(time_windows):
            index = manager.NodeToIndex(node_idx)
            time_dim.CumulVar(index).SetRange(tw_open, tw_close)

        # Fix each vehicle's start to exactly _DAY_START_MINUTES
        for v in range(trip_days):
            time_dim.CumulVar(routing.Start(v)).SetRange(
                _DAY_START_MINUTES, _DAY_START_MINUTES
            )
            time_dim.CumulVar(routing.End(v)).SetRange(
                _DAY_START_MINUTES, _DAY_END_MINUTES
            )

        # Capacity: max stops per vehicle
        def demand_callback(from_index: int) -> int:
            return 0 if manager.IndexToNode(from_index) == 0 else 1

        demand_idx = routing.RegisterUnaryTransitCallback(demand_callback)
        routing.AddDimensionWithVehicleCapacity(
            demand_idx,
            0,
            [max_per_day] * trip_days,
            True,
            "Capacity",
        )

        # Search parameters
        params = pywrapcp.DefaultRoutingSearchParameters()
        params.first_solution_strategy = (
            routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
        )
        params.local_search_metaheuristic = (
            routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
        )
        params.time_limit.seconds = _VRP_SOLVER_TIME_LIMIT_SECONDS

        solution = routing.SolveWithParameters(params)

        if not solution:
            logger.warning("OR-Tools returned no solution — falling back to greedy ordering.")
            return _greedy_fallback(candidates, trip_context)

        return self._extract_solution(
            manager, routing, solution, candidates,
            time_dim, trip_days, mode, start_date,
        )

    # --- Solution extraction ---

    @staticmethod
    def _extract_solution(
        manager:    pywrapcp.RoutingIndexManager,
        routing:    pywrapcp.RoutingModel,
        solution:   Any,
        candidates: list[PlaceRecord],
        time_dim:   Any,
        trip_days:  int,
        mode:       str,
        start_date: str | None,
    ) -> list[dict]:
        days_out: list[dict] = []

        for vehicle in range(trip_days):
            ordered:       list[PlaceRecord] = []
            arrival_times: list[int]         = []

            index = routing.Start(vehicle)
            while not routing.IsEnd(index):
                node = manager.IndexToNode(index)
                if node != 0:  # skip depot
                    ordered.append(candidates[node - 1])
                    arrival_times.append(solution.Min(time_dim.CumulVar(index)))
                index = solution.Value(routing.NextVar(index))

            if not ordered:
                continue

            days_out.append(
                _build_day(ordered, vehicle, mode, start_date, arrival_times)
            )

        return days_out
