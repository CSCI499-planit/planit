# Stage 4: Itinerary Optimization  (TODO)
#
# Input:  ranked places from Stage 3 + trip context
# Output: day-by-day itinerary with estimated times and travel legs
#
# Plan: Google OR-Tools VRP (Vehicle Routing Problem with Time Windows)
#   Constraints:
#     - Place opening hours                  (time windows per node)
#     - max_travel_minutes between stops     (from user survey)
#     - travel_mode                          (walk / bike / transit / drive)
#     - max_places_per_day                   (from itinerary_pace: 2 / 4 / 6)
#     - trip_budget_tier                     (cumulative cost constraint)
#
#   Routing data:
#     - Travel times and distances from Geoapify Routing API
#     - One VRP solve per day of the trip
#
# Output schema (one entry per day):
#   {
#     "day": 1,
#     "date": "2024-06-15",
#     "stops": [
#       {
#         "place":          PlaceRecord,
#         "arrival_time":   "10:00",
#         "departure_time": "11:30",
#         "travel_to_next": {"mode": "walk", "minutes": 12, "distance_m": 950}
#       },
#       ...
#     ],
#     "total_budget_estimate": 85.0
#   }
