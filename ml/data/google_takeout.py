from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from ml.data.preprocess import UserVisit

logger = logging.getLogger(__name__)

# dwell time → implicit rating; short stays are likely pass-bys
_DURATION_RATING_BREAKPOINTS: list[tuple[int, float]] = [
    (5,  1.5),   # < 5 min  — probably just drove past
    (15, 2.5),   # 5–15     — quick stop
    (45, 3.5),   # 15–45    — normal visit
    (90, 4.0),   # 45–90    — extended visit
]
_DURATION_MAX_RATING: float = 4.5  # 90+ min

# keyword → tags for place names when no category data is available
_NAME_KEYWORDS_TO_TAGS: dict[str, list[str]] = {
    # food & drink
    "restaurant":    ["food_and_drink"],
    "kitchen":       ["food_and_drink"],
    "grill":         ["food_and_drink"],
    "eatery":        ["food_and_drink"],
    "bistro":        ["food_and_drink"],
    "diner":         ["food_and_drink"],
    "buffet":        ["food_and_drink"],
    "sushi":         ["food_and_drink"],
    "pizza":         ["food_and_drink"],
    "burger":        ["food_and_drink", "quick_visit"],
    "empanada":      ["food_and_drink"],
    "shawarma":      ["food_and_drink"],
    "gyro":          ["food_and_drink"],
    "halal":         ["food_and_drink"],
    "baguette":      ["food_and_drink", "quick_visit"],
    "bakery":        ["food_and_drink", "quick_visit"],
    "bites":         ["food_and_drink"],
    "cafe":          ["food_and_drink", "quick_visit"],
    "café":          ["food_and_drink", "quick_visit"],
    "coffee":        ["food_and_drink", "quick_visit"],
    "starbucks":     ["food_and_drink", "quick_visit"],
    "mcdonald":      ["food_and_drink", "quick_visit", "budget_friendly"],
    "chick-fil-a":   ["food_and_drink", "quick_visit", "budget_friendly"],
    "subway":        ["food_and_drink", "quick_visit", "budget_friendly"],
    "burger king":   ["food_and_drink", "quick_visit", "budget_friendly"],
    "panda express": ["food_and_drink", "quick_visit"],
    "olive garden":  ["food_and_drink"],
    # nightlife
    "bar":           ["nightlife", "food_and_drink"],
    "lounge":        ["nightlife"],
    "hookah":        ["nightlife"],
    "club":          ["nightlife"],
    "brewery":       ["nightlife", "food_and_drink"],
    # outdoor
    "park":          ["outdoor", "scenic", "pet_friendly"],
    "playground":    ["outdoor", "family_friendly"],
    "beach":         ["outdoor", "scenic", "adventurous"],
    "garden":        ["outdoor", "scenic", "romantic"],
    "pier":          ["outdoor", "scenic"],
    "trail":         ["outdoor", "adventurous"],
    # shopping
    "mall":          ["shopping"],
    "plaza":         ["shopping"],
    "market":        ["shopping", "food_and_drink"],
    "ikea":          ["shopping"],
    # wellness / fitness
    "gym":           ["wellness"],
    "fitness":       ["wellness"],
    "yoga":          ["wellness"],
    "spa":           ["wellness", "upscale"],
    "physical therapy": ["wellness"],
    "sports club":   ["wellness"],
    "climbing":      ["wellness", "adventurous", "outdoor"],
    "movement":      ["wellness", "adventurous"],
    # cultural
    "museum":        ["cultural", "historical"],
    "gallery":       ["cultural"],
    "theatre":       ["cultural"],
    "theater":       ["cultural"],
    "cinema":        ["cultural", "quick_visit"],
    "regal":         ["cultural", "quick_visit"],
    # adventurous / family
    "adventure park": ["adventurous", "family_friendly"],
    "amusement":     ["adventurous", "family_friendly"],
    "thrillz":       ["adventurous", "family_friendly"],
    "fair":          ["family_friendly", "shopping"],
}


def _parse_duration_minutes(duration: dict[str, Any]) -> float:
    # Takeout format: {"startTimestamp": "2024-03-01T14:00:00Z", "endTimestamp": "..."}
    try:
        start = datetime.fromisoformat(duration["startTimestamp"].replace("Z", "+00:00"))
        end   = datetime.fromisoformat(duration["endTimestamp"].replace("Z", "+00:00"))
        return max((end - start).total_seconds() / 60.0, 0.0)
    except (KeyError, ValueError, AttributeError):
        return 0.0


def _duration_to_implicit_rating(minutes: float) -> float:
    for threshold, rating in _DURATION_RATING_BREAKPOINTS:
        if minutes < threshold:
            return rating
    return _DURATION_MAX_RATING


def _infer_tags_from_name(name: str) -> list[str]:
    name_lower = name.lower()
    tags: set[str] = set()
    for keyword, mapped in _NAME_KEYWORDS_TO_TAGS.items():
        if keyword in name_lower:
            tags.update(mapped)
    return list(tags)


def parse_google_takeout(
    takeout_data:   dict[str, Any] | list[dict[str, Any]],
    user_id:        str,
    place_tag_db:   dict[str, list[str]],
    min_confidence: float = 50.0,
) -> list[UserVisit]:
    """Parse Google Takeout Timeline JSON into UserVisit records.

    Accepts a single month dict or a list of month dicts (merged by the caller).
    Dwell time is converted to an implicit rating — longer stays signal stronger interest.
    """
    months = [takeout_data] if isinstance(takeout_data, dict) else takeout_data
    aggregated: dict[str, dict[str, Any]] = {}

    for month in months:
        for obj in month.get("timelineObjects", []):
            pv = obj.get("placeVisit")
            if pv is None:
                continue
            if float(pv.get("visitConfidence", 0)) < min_confidence:
                continue

            loc      = pv.get("location", {})
            place_id = loc.get("placeId", "")
            name     = loc.get("name", "").strip()
            if not place_id and not name:
                continue

            key = place_id or name
            if key not in aggregated:
                fallback_id = f"gmap_{name.lower().replace(' ', '_')}" if not place_id else place_id
                aggregated[key] = {
                    "place_id":  fallback_id,
                    "tags":      place_tag_db.get(place_id, []),
                    "durations": [],
                    "count":     0,
                }
            aggregated[key]["durations"].append(_parse_duration_minutes(pv.get("duration", {})))
            aggregated[key]["count"] += 1

    visits: list[UserVisit] = []
    for agg in aggregated.values():
        durations = agg["durations"]
        avg_dur   = sum(durations) / len(durations) if durations else 0.0
        visits.append(UserVisit(
            user_id=user_id,
            place_id=agg["place_id"],
            rating=_duration_to_implicit_rating(avg_dur),
            visit_count=agg["count"],
            tags=agg["tags"],
        ))

    logger.info("Parsed %d unique places from Takeout for user %s", len(visits), user_id)
    return visits


def parse_google_reviews(
    reviews_data: dict[str, Any],
    user_id:      str,
) -> list[UserVisit]:
    """Parse Google Maps Reviews.json into UserVisit records.

    File lives at Takeout/Maps/Reviews.json.
    Uses five_star_rating_published as the explicit rating; tags inferred from place name.
    """
    visits: list[UserVisit] = []
    seen: set[str] = set()

    for feature in reviews_data.get("features", []):
        props  = feature.get("properties", {})
        coords = feature.get("geometry", {}).get("coordinates", [0, 0])

        if coords == [0, 0] or "location" not in props:
            continue

        loc    = props["location"]
        name   = loc.get("name", "").strip()
        rating = props.get("five_star_rating_published")

        if not name or rating is None:
            continue

        key = name.lower()
        if key in seen:
            continue
        seen.add(key)

        place_id = f"gmap_{name.lower().replace(' ', '_').replace('/', '_')}"
        visits.append(UserVisit(
            user_id=user_id,
            place_id=place_id,
            rating=float(rating),
            visit_count=1,
            tags=_infer_tags_from_name(name),
        ))

    logger.info("Parsed %d places from Reviews.json for user %s", len(visits), user_id)
    return visits


def parse_google_saved_places(
    saved_data: dict[str, Any],
    user_id:    str,
) -> list[UserVisit]:
    """Parse Google Maps Saved Places.json into UserVisit records.

    File lives at Takeout/Maps/Saved Places.json.
    No explicit rating — saved = implicit 3.5 (interested but unrated).
    """
    visits: list[UserVisit] = []
    seen: set[str] = set()

    for feature in saved_data.get("features", []):
        props  = feature.get("properties", {})
        coords = feature.get("geometry", {}).get("coordinates", [0, 0])

        if coords == [0, 0] or "location" not in props:
            continue

        name = props["location"].get("name", "").strip()
        if not name:
            continue

        key = name.lower()
        if key in seen:
            continue
        seen.add(key)

        place_id = f"gmap_{name.lower().replace(' ', '_').replace('/', '_')}"
        visits.append(UserVisit(
            user_id=user_id,
            place_id=place_id,
            rating=3.5,
            visit_count=1,
            tags=_infer_tags_from_name(name),
        ))

    logger.info("Parsed %d places from Saved Places.json for user %s", len(visits), user_id)
    return visits
