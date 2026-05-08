# Stage 4 — Itinerary Optimization (OR-Tools VRPTW)
# One vehicle per trip day. Falls back to greedy nearest-neighbor if OR-Tools
# returns no solution (e.g. over-constrained by tight time windows).
from __future__ import annotations

import logging
import math
import os
import re
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

if TYPE_CHECKING:
    from ml.data.preprocess import PlaceRecord

from ml.models.user_profiler import PACE_TO_MAX_PLACES
from ml.services.azure_maps_client import (
    AzureMapsError,
    UnsupportedTravelModeError,
    build_time_matrix as _azure_build_time_matrix,
)

logger = logging.getLogger(__name__)

_TRAVEL_SPEED_KMH: dict[str, float] = {
    "walk":    4.5,
    "bike":   15.0,
    "transit": 25.0,
    "drive":   30.0,
}


_TAG_DWELL_MINUTES: dict[str, int] = {
    "quick_visit":     30,
    "food_and_drink":  60,
    "cultural":        90,
    "historical":      90,
    "outdoor":         60,
    "scenic":          60,
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
_CANDIDATE_BUFFER_PER_DAY: int = 2
_LONG_ARC_PENALTY: int = 10_000

# Max food_and_drink stops per day by pace
_MAX_FOOD_PER_DAY: dict[str, int] = {
    "relaxed":  1,
    "balanced": 1,
    "packed":   2,
}


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
    speed = _TRAVEL_SPEED_KMH.get(mode, 25.0)
    return max(1, round((dist_km / speed) * 60))


def _build_haversine_matrix(
    coords: list[tuple[float, float]],
    travel_mode: str,
    max_travel_min: int = 90,
) -> list[list[int]]:
    speed = _TRAVEL_SPEED_KMH.get(travel_mode, 25.0)
    n = len(coords)
    matrix: list[list[int]] = []
    for i in range(n):
        row = []
        for j in range(n):
            if i == j:
                row.append(0)
            else:
                dist_km = _haversine_km(coords[i][0], coords[i][1], coords[j][0], coords[j][1])
                raw_time = max(1, round((dist_km / speed) * 60))
                if j != 0 and raw_time > max_travel_min:
                    row.append(raw_time + _LONG_ARC_PENALTY)
                else:
                    row.append(raw_time)
        matrix.append(row)
    return matrix


def _dwell_minutes(place: PlaceRecord) -> int:
    times = [_TAG_DWELL_MINUTES[t] for t in (place.get("tags") or []) if t in _TAG_DWELL_MINUTES]
    return max(times) if times else _DEFAULT_DWELL_MINUTES


def _filter_open_during_day(
    places:        list["PlaceRecord"],
    day_start_min: int = _DAY_START_MINUTES,
    day_end_min:   int = _DAY_END_MINUTES,
) -> list["PlaceRecord"]:
    open_places = [
        p for p in places
        if _arrival_window(p, day_start_min, day_end_min) is not None
    ]
    return open_places if open_places else places


_CATEGORY_DEFAULT_WINDOWS: list[tuple[list[str], tuple[int, int]]] = [
    (["entertainment.museum", "tourism.museum",
     "cultural", "museum"],  (10 * 60, 18 * 60)),
    (["tourism.sights", "tourism.attraction",
     "historical"],            (8 * 60, 20 * 60)),
    (["catering.bar", "catering.pub", "catering.nightclub",
     "nightlife"], (18 * 60, 24 * 60)),
    (["catering", "restaurant", "food", "coffee"],
     (11 * 60, 22 * 60)),
    (["leisure.park", "natural.", "leisure.garden"],
     (6 * 60, 21 * 60)),
    (["commercial.shopping_mall", "commercial.marketplace",
     "shopping"], (10 * 60, 21 * 60)),
    (["sport.fitness", "wellness"],
     (6 * 60, 22 * 60)),
]


def _category_default_window(place: "PlaceRecord") -> tuple[int, int]:
    cats = [c.lower() for c in (place.get("categories") or [])]
    for patterns, window in _CATEGORY_DEFAULT_WINDOWS:
        if any(any(pat in cat for cat in cats) for pat in patterns):
            return window
    return (_DAY_START_MINUTES, _DAY_END_MINUTES)


def _parse_time_window(hours: str | None, place: "PlaceRecord | None" = None) -> tuple[int, int]:
    # best-effort parse of an OSM hours string → (open, close) minutes from midnight
    # falls back to category-aware defaults when format isn't recognised
    if not hours:
        return _category_default_window(place) if place else (_DAY_START_MINUTES, _DAY_END_MINUTES)

    # look for HH:MM-HH:MM or H:MM-H:MM
    m = re.search(r"(\d{1,2}):(\d{2})\s*[-–]\s*(\d{1,2}):(\d{2})", hours)
    if m:
        open_min = int(m.group(1)) * 60 + int(m.group(2))
        close_min = int(m.group(3)) * 60 + int(m.group(4))
        if open_min < close_min:
            return (open_min, close_min)

    # look for 9am-9pm style
    m = re.search(
        r"(\d{1,2})(am|pm)\s*[-–]\s*(\d{1,2})(am|pm)", hours, re.IGNORECASE)
    if m:
        def to_24h(h: int, period: str) -> int:
            if period.lower() == "pm" and h != 12:
                return h + 12
            if period.lower() == "am" and h == 12:
                return 0
            return h
        open_min = to_24h(int(m.group(1)), m.group(2)) * 60
        close_min = to_24h(int(m.group(3)), m.group(4)) * 60
        if open_min < close_min:
            return (open_min, close_min)

    return _category_default_window(place) if place else (_DAY_START_MINUTES, _DAY_END_MINUTES)


def _arrival_window(
    place:         "PlaceRecord",
    day_start_min: int = _DAY_START_MINUTES,
    day_end_min:   int = _DAY_END_MINUTES,
) -> tuple[int, int] | None:
    tw_open, tw_close = _parse_time_window(place.get("hours"), place)
    latest = min(tw_close - _dwell_minutes(place), day_end_min)
    earliest = max(tw_open, day_start_min)
    if latest < earliest:
        return None
    return earliest, latest


def _minutes_to_time(minutes: int) -> str:
    h = (minutes // 60) % 24
    m = minutes % 60
    return f"{h:02d}:{m:02d}"


def _parse_max_travel_minutes(raw: str) -> int:
    raw = str(raw).strip().lower()
    if "< 10" in raw or "<10" in raw:
        return 10
    if "10" in raw and "20" in raw:
        return 20
    if "20" in raw and "40" in raw:
        return 40
    return 90  # "> 40" or unrecognised gives generous cap


def _nearest_neighbor_order(
    places:         list[PlaceRecord],
    mode:           str = "transit",
    max_travel_min: int = 90,
) -> list[PlaceRecord]:
    if len(places) <= 1:
        return list(places)
    remaining = list(places)
    ordered = [remaining.pop(0)]
    while remaining:
        last = ordered[-1]
        travel_times = [
            _travel_minutes(
                last.get("latitude", 0.0), last.get("longitude", 0.0),
                remaining[i].get("latitude", 0.0), remaining[i].get("longitude", 0.0),
                mode,
            )
            for i in range(len(remaining))
        ]
        # prefer places within the user's travel budget; fall back to nearest if none qualify
        within = [(i, t) for i, t in enumerate(
            travel_times) if t <= max_travel_min]
        best_idx = min(within, key=lambda x: x[1])[0] if within else int(
            min(range(len(remaining)), key=lambda i: travel_times[i])
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
    stops: list[dict] = []
    _greedy_time = _DAY_START_MINUTES  # running clock for greedy mode

    for i, place in enumerate(places):
        if arrival_times:
            arr_min = arrival_times[i]
        else:
            arr_min = _greedy_time

        dwell = _dwell_minutes(place)
        dep_min = arr_min + dwell

        travel_to_next = None
        if i < len(places) - 1:
            nxt = places[i + 1]
            t_min = _travel_minutes(
                place.get("latitude", 0.0), place.get("longitude", 0.0),
                nxt.get("latitude", 0.0),   nxt.get("longitude", 0.0),
                mode,
            )
            dist_m = round(_haversine_km(
                place.get("latitude", 0.0), place.get("longitude", 0.0),
                nxt.get("latitude", 0.0),   nxt.get("longitude", 0.0),
            ) * 1000)
            travel_to_next = {"mode": mode,
                              "duration_minutes": t_min, "distance_m": dist_m}
            if not arrival_times:
                _greedy_time = dep_min + t_min

        stops.append({
            "place":          place,
            "arrival_time":   _minutes_to_time(arr_min),
            "departure_time": _minutes_to_time(dep_min),
            "travel_to_next": travel_to_next,
        })

    date_str: str | None = None
    if start_date:
        try:
            base = datetime.strptime(start_date, "%Y-%m-%d")
            date_str = (base + timedelta(days=day_idx)).strftime("%Y-%m-%d")
        except ValueError:
            pass

    return {"day": day_idx + 1, "date": date_str, "stops": stops}


def _build_greedy_day(
    places:     list[PlaceRecord],
    day_idx:    int,
    mode:       str,
    start_date: str | None,
) -> dict | None:
    scheduled: list[PlaceRecord] = []
    arrivals:  list[int] = []
    current = _DAY_START_MINUTES
    prev: PlaceRecord | None = None

    for place in places:
        window = _arrival_window(place)
        if window is None:
            continue
        travel = (
            _travel_minutes(
                prev.get("latitude", 0.0), prev.get("longitude", 0.0),
                place.get("latitude", 0.0), place.get("longitude", 0.0),
                mode,
            )
            if prev else 0
        )
        arr_min = max(current + travel, window[0])
        if arr_min > window[1]:
            continue
        scheduled.append(place)
        arrivals.append(arr_min)
        current = arr_min + _dwell_minutes(place)
        prev = place

    if not scheduled:
        return None
    return _build_day(scheduled, day_idx, mode, start_date, arrivals)


def _greedy_fallback(candidates: list[PlaceRecord], trip_context: dict) -> list[dict]:
    pace = trip_context.get("itinerary_pace", "balanced")
    max_per_day = PACE_TO_MAX_PLACES.get(pace, 4)
    modes = trip_context.get("travel_mode") or ["transit"]
    mode = modes[0] if isinstance(modes, list) else modes
    trip_days = int(trip_context.get("trip_days", 1))
    start_date = trip_context.get("start_date")
    max_travel_min = _parse_max_travel_minutes(
        trip_context.get("max_travel_minutes", "> 40"))
    hotel_loc = trip_context.get("hotel_location")

    candidates = _filter_open_during_day(candidates)

    days_out = []
    for day_idx in range(trip_days):
        day_places = candidates[day_idx * max_per_day: (day_idx + 1) * max_per_day]
        if not day_places:
            break
        if hotel_loc:
            day_places = sorted(
                day_places,
                key=lambda p: _haversine_km(
                    float(hotel_loc["latitude"]), float(hotel_loc["longitude"]),
                    p.get("latitude", 0.0), p.get("longitude", 0.0),
                ),
            )
        ordered = _nearest_neighbor_order(
            day_places, mode=mode, max_travel_min=max_travel_min)
        ordered = _position_food_stops(ordered)
        day = _build_greedy_day(ordered, day_idx, mode, start_date)
        if day:
            days_out.append(day)
    return days_out


def _is_food(place: "PlaceRecord") -> bool:
    return "food_and_drink" in (place.get("tags") or [])


def _ensure_food_stop(
    ranked_places: list[PlaceRecord],
    total_slots:   int,
    trip_days:     int,
    pace:          str = "balanced",
) -> list[PlaceRecord]:
    """Guarantee at least 1 food stop per day, and cap food stops at _MAX_FOOD_PER_DAY."""
    max_food = _MAX_FOOD_PER_DAY.get(pace, 1)
    slots_per_day = total_slots // trip_days if trip_days else total_slots
    candidates = list(ranked_places[:total_slots])
    used_ids = {p.get("place_id") for p in candidates}

    for day in range(trip_days):
        day_start = day * slots_per_day
        day_end   = day_start + slots_per_day
        day_slice = candidates[day_start:day_end]

        food_idxs     = [i for i, p in enumerate(day_slice) if _is_food(p)]
        non_food_idxs = [i for i, p in enumerate(day_slice) if not _is_food(p)]

        # --- cap: remove excess food stops above max_food ---
        while len(food_idxs) > max_food:
            excess_i = food_idxs.pop()  # lowest-ranked food stop
            replacement = next(
                (p for p in ranked_places
                 if not _is_food(p) and p.get("place_id") not in used_ids),
                None,
            )
            used_ids.discard(candidates[day_start + excess_i].get("place_id"))
            if replacement:
                candidates[day_start + excess_i] = replacement
                used_ids.add(replacement.get("place_id"))
                non_food_idxs.append(excess_i)
                logger.info("Capped food stops: replaced '%s' with '%s' on day %d.",
                            candidates[day_start + excess_i].get("name"),
                            replacement.get("name"), day + 1)
            else:
                candidates.pop(day_start + excess_i)

        # --- guarantee: inject food stop if none present ---
        if not food_idxs:
            food_place = next(
                (p for p in ranked_places
                 if _is_food(p) and p.get("place_id") not in used_ids),
                None,
            )
            if food_place and non_food_idxs:
                replace_i = non_food_idxs[-1]  # lowest-ranked non-food
                used_ids.discard(candidates[day_start + replace_i].get("place_id"))
                candidates[day_start + replace_i] = food_place
                used_ids.add(food_place.get("place_id"))
                logger.info("Injected food stop '%s' into day %d.",
                            food_place.get("name"), day + 1)

    return candidates


def _position_food_stops(ordered: list["PlaceRecord"]) -> list["PlaceRecord"]:
    """Move food stops to evenly-spaced middle positions (lunch/dinner slots)."""
    food = [p for p in ordered if _is_food(p)]
    non_food = [p for p in ordered if not _is_food(p)]
    n = len(ordered)
    if not food or n < 2:
        return ordered

    # For 1 food stop → middle; for 2 → 1/3 and 2/3 positions
    positions = [n // (len(food) + 1) * (i + 1) for i in range(len(food))]
    result = list(non_food)
    for pos, place in zip(positions, food):
        result.insert(min(pos, len(result)), place)
    return result


def _candidate_pool(
    ranked_places: list[PlaceRecord],
    max_per_day:   int,
    trip_days:     int,
    pace:          str = "balanced",
) -> list[PlaceRecord]:
    total_slots = max_per_day * trip_days
    candidates = _ensure_food_stop(ranked_places, total_slots, trip_days, pace)
    used_ids = {p.get("place_id") for p in candidates}
    buffer = _CANDIDATE_BUFFER_PER_DAY * trip_days
    for p in ranked_places:
        if len(candidates) >= total_slots + buffer:
            break
        pid = p.get("place_id")
        if pid in used_ids:
            continue
        candidates.append(p)
        used_ids.add(pid)
    return candidates


class RouteOptimizer:

    def optimize(
        self,
        ranked_places: list[PlaceRecord],
        trip_context:  dict,
    ) -> list[dict]:
        # Option A — deduplicate by place_id before anything else
        seen: set[str] = set()
        deduped: list[PlaceRecord] = []
        for p in ranked_places:
            pid = p.get("place_id", "")
            if not pid or pid not in seen:
                if pid:
                    seen.add(pid)
                deduped.append(p)
        ranked_places = deduped

        # Option B — per-day routing when revisits are allowed
        if trip_context.get("allow_revisits") and int(trip_context.get("trip_days", 1)) > 1:
            return self._optimize_with_revisits(ranked_places, trip_context)

        pace = trip_context.get("itinerary_pace", "balanced")
        max_per_day = PACE_TO_MAX_PLACES.get(pace, 4)
        modes = trip_context.get("travel_mode") or ["transit"]
        mode = modes[0] if isinstance(modes, list) else modes
        trip_days = int(trip_context.get("trip_days", 1))
        start_date = trip_context.get("start_date")
        max_travel_min = _parse_max_travel_minutes(
            trip_context.get("max_travel_minutes", "> 40"))

        candidates = _candidate_pool(ranked_places, max_per_day, trip_days, pace)
        candidates = [p for p in candidates if _arrival_window(p) is not None]
        if not candidates:
            return []
        if len(candidates) == 1:
            day = _build_greedy_day(candidates, 0, mode, start_date)
            return [day] if day else []

        hotel_loc = trip_context.get("hotel_location")
        if hotel_loc:
            depot_lat = float(hotel_loc["latitude"])
            depot_lon = float(hotel_loc["longitude"])
        else:
            all_lats  = [p.get("latitude", 0.0) for p in candidates]
            all_lons  = [p.get("longitude", 0.0) for p in candidates]
            depot_lat = sum(all_lats) / len(all_lats)
            depot_lon = sum(all_lons) / len(all_lons)

        locations = [(depot_lat, depot_lon)] + [(p.get("latitude",
                                                       0.0), p.get("longitude", 0.0)) for p in candidates]
        n = len(locations)

        fallback_enabled = os.getenv("AZURE_MATRIX_FALLBACK_ENABLED", "true").lower() == "true"
        try:
            raw_matrix = _azure_build_time_matrix(locations, mode)
            time_matrix = [row[:] for row in raw_matrix]
            for i in range(n):
                for j in range(n):
                    if i != j and j != 0 and time_matrix[i][j] > max_travel_min:
                        time_matrix[i][j] += _LONG_ARC_PENALTY
        except UnsupportedTravelModeError:
            time_matrix = _build_haversine_matrix(locations, mode, max_travel_min)
        except AzureMapsError as e:
            if fallback_enabled:
                logger.warning("Azure matrix unavailable (%s), falling back to haversine", e)
                time_matrix = _build_haversine_matrix(locations, mode, max_travel_min)
            else:
                raise

        service_times = [0] + [_dwell_minutes(p) for p in candidates]

        time_windows = [(_DAY_START_MINUTES, _DAY_START_MINUTES)]
        for p in candidates:
            window = _arrival_window(p)
            if window is None:
                logger.warning("Skipping impossible time window for %s", p.get("name"))
                continue
            time_windows.append(window)

        manager = pywrapcp.RoutingIndexManager(n, trip_days, 0)
        routing = pywrapcp.RoutingModel(manager)

        def time_callback(from_index: int, to_index: int) -> int:
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            return time_matrix[from_node][to_node] + service_times[from_node]

        transit_idx = routing.RegisterTransitCallback(time_callback)
        routing.SetArcCostEvaluatorOfAllVehicles(transit_idx)

        routing.AddDimension(
            transit_idx,
            60,
            24 * 60,
            False,
            "Time",
        )
        time_dim = routing.GetDimensionOrDie("Time")

        for node_idx, (tw_open, tw_close) in enumerate(time_windows):
            index = manager.NodeToIndex(node_idx)
            time_dim.CumulVar(index).SetRange(tw_open, tw_close)

        for v in range(trip_days):
            time_dim.CumulVar(routing.Start(v)).SetRange(
                _DAY_START_MINUTES, _DAY_START_MINUTES
            )
            time_dim.CumulVar(routing.End(v)).SetRange(
                _DAY_START_MINUTES, _DAY_END_MINUTES
            )

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

        for node in range(1, n):
            score = float(candidates[node - 1].get("score") or 0.0)
            rank_bonus = max(0, len(candidates) - node)
            penalty = 1_000 + int(score * 10_000) + rank_bonus
            routing.AddDisjunction([manager.NodeToIndex(node)], penalty)

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
            logger.warning(
                "OR-Tools returned no solution — falling back to greedy ordering.")
            return _greedy_fallback(candidates, trip_context)

        days_out = self._extract_solution(
            manager, routing, solution, candidates,
            time_dim, trip_days, mode, start_date,
        )
        if not days_out:
            logger.warning(
                "OR-Tools dropped all nodes (trivial solution) — falling back to greedy ordering.")
            return _greedy_fallback(candidates, trip_context)
        return days_out

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
            arrival_times: list[int] = []

            index = routing.Start(vehicle)
            while not routing.IsEnd(index):
                node = manager.IndexToNode(index)
                if node != 0:
                    ordered.append(candidates[node - 1])
                    arrival_times.append(
                        solution.Min(time_dim.CumulVar(index)))
                index = solution.Value(routing.NextVar(index))

            if not ordered:
                continue

            days_out.append(
                _build_day(ordered, vehicle, mode, start_date, arrival_times)
            )

        return days_out

    def _optimize_with_revisits(
        self,
        ranked_places: list[PlaceRecord],
        trip_context:  dict,
    ) -> list[dict]:
        # per-day greedy routing — food_and_drink places can repeat across days,
        # all other categories are locked after their first scheduled appearance
        pace = trip_context.get("itinerary_pace", "balanced")
        max_per_day = PACE_TO_MAX_PLACES.get(pace, 4)
        modes = trip_context.get("travel_mode") or ["transit"]
        mode = modes[0] if isinstance(modes, list) else modes
        trip_days = int(trip_context.get("trip_days", 1))
        start_date = trip_context.get("start_date")
        max_travel_min = _parse_max_travel_minutes(
            trip_context.get("max_travel_minutes", "> 40"))

        seen_non_food: set[str] = set()
        days_out: list[dict] = []

        for day_idx in range(trip_days):
            day_pool = [
                p for p in ranked_places
                if p.get("place_id") not in seen_non_food
            ]
            day_candidates = _ensure_food_stop(day_pool, max_per_day, 1, pace)
            if not day_candidates:
                break

            for p in day_candidates:
                if not _is_food(p):
                    pid = p.get("place_id", "")
                    if pid:
                        seen_non_food.add(pid)

            ordered = _nearest_neighbor_order(
                day_candidates, mode=mode, max_travel_min=max_travel_min)
            ordered = _position_food_stops(ordered)
            day = _build_greedy_day(ordered, day_idx, mode, start_date)
            if day:
                days_out.append(day)

        return days_out
