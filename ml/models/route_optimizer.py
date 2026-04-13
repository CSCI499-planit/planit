"""
Stage 4 — Itinerary Optimization (not yet implemented)

Plan: OR-Tools VRP with time windows, one solve per trip day.

Constraints:
  - Place opening hours        (time windows per node)
  - max_travel_minutes         (from user survey)
  - travel_mode                (walk / bike / transit / drive)
  - max_places_per_day         (pace: relaxed=2, balanced=4, packed=6)
  - trip_budget_tier           (cumulative cost constraint)

Routing data: Geoapify Routing API for travel times between stops.

Output shape (one entry per day):
  {
    "day": 1,
    "date": "2024-06-15",
    "stops": [
      {
        "place":          PlaceRecord,
        "arrival_time":   "10:00",
        "departure_time": "11:30",
        "travel_to_next": {"mode": "walk", "minutes": 12, "distance_m": 950}
      }
    ],
    "total_budget_estimate": 85.0
  }
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ml.data.preprocess import PlaceRecord


class RouteOptimizer:

    def optimize(
        self,
        ranked_places: list[PlaceRecord],
        trip_context:  dict,
    ) -> list[dict]:
        raise NotImplementedError("Stage 4 not yet implemented.")
