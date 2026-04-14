from __future__ import annotations

import csv
import os
import sys
import uuid
from datetime import datetime, timezone
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

_USE_CASE = {
    "Discovering things to do locally":           "local",
    "Day trips or short outings outside my city": "daytrip",
    "Planning long trips (overnight/multiday)":   "travel",
    "All of the above":                           "mixed",
}

_PARTY_TYPE = {
    "Myself (solo)":             "solo",
    "Me and a partner (couple)": "couple",
    "Group of friends":          "friends",
    "Family with kids":          "family",
    "Multiple/Varying groups":   "mixed",
}

_DAILY_BUDGET = {
    "Free or nearly free": 1,
    "Budget-conscious":    1,
    "Moderate":            2,
    "Comfortable":         3,
    "No limit":            4,
}

_TRIP_BUDGET = {
    "Budget (< $500)":                                 1,
    "Moderate ($500 - $1,500)":                        2,
    "Comfortable ($1,500 - $3,000)":                   3,
    "Luxury ($3,000+)":                                4,
    "Not applicable (I primarily use PlanIt locally)": None,
}

_ACTIVITY_TO_TAG = {
    "Outdoor adventures (hiking, parks, nature)":                    "outdoor",
    "Art, galleries, museums & cultural experiences":                "cultural",
    "Restaurants, cafes, food halls & culinary spots":               "food_and_drink",
    "Bars, live music, comedy shows & nightlife":                    "nightlife",
    "Shopping, markets, thrift stores & pop-ups":                    "shopping",
    "Wellness (fitness, meditation, yoga)":                          "wellness",
    "History, architecture & heritage sites":                        "historical",
    "Scenic spots (viewpoints, nature)":                             "scenic",
    "Adventurous activities (climbing, extreme sports, challenges)":  "adventurous",
    "Family-friendly spots":                                         "family_friendly",
    "Romantic settings (date spots)":                                "romantic",
    "Dog-friendly spaces":                                           "pet_friendly",
    "Upscale & luxury places":                                       "upscale",
    "Budget-friendly spots":                                         "budget_friendly",
}

_CUISINE_PREFIXES = [
    ("American",         "american"),
    ("Italian",          "italian"),
    ("East Asian",       "east asian"),
    ("Southeast Asian",  "southeast asian"),
    ("Mexican",          "mexican"),
    ("Indian",           "indian"),
    ("Mediterranean",    "mediterranean"),
    ("Vegetarian Focus", "vegetarian"),
    ("Seafood Focus",    "seafood"),
]

_DIETARY_PREFIXES = [
    ("Vegetarian", "vegetarian"),
    ("Vegan",      "vegan"),
    ("Gluten",     "gluten_free"),
    ("Halal",      "halal"),
    ("Kosher",     "kosher"),
    ("Nut",        "nut_allergy"),
    ("Dairy",      "dairy_free"),
]

_TRAVEL_MODE_PREFIXES = [
    ("Walking",  "walk"),
    ("Biking",   "bike"),
    ("Transit",  "transit"),
    ("Driving",  "drive"),
]

_MAX_TRAVEL = {
    "<10 minutes":     "< 10",
    "< 10 minutes":    "< 10",
    "10-20 minutes":   "10-20",
    "20 - 40 minutes": "20-40",
    "> 40 minutes":    "> 40",
}

_PACE_PREFIXES = [
    ("Packed",   "packed"),
    ("Balanced", "balanced"),
    ("Relaxed",  "relaxed"),
]


def _map_activities(cell: str) -> list[str]:
    tags, seen = [], set()
    for label, tag in _ACTIVITY_TO_TAG.items():
        if label.lower() in cell.lower() and tag not in seen:
            seen.add(tag)
            tags.append(tag)
    return tags


def _map_prefixes(cell: str, prefixes: list[tuple[str, str]]) -> list[str]:
    result, seen = [], set()
    for prefix, val in prefixes:
        if prefix.lower() in cell.lower() and val not in seen:
            seen.add(val)
            result.append(val)
    return result


def _find_col(headers: list[str], question_num: int) -> str:
    prefix = f"{question_num}."
    for h in headers:
        if h.strip().startswith(prefix):
            return h
    raise KeyError(f"Column for Q{question_num} not found.")


def transform_row(row: dict, headers: list[str]) -> dict:
    def q(n: int) -> str:
        return row.get(_find_col(headers, n), "").strip()

    pace = "balanced"
    for prefix, val in _PACE_PREFIXES:
        if prefix.lower() in q(12).lower():
            pace = val
            break

    return {
        "id":                   str(uuid.uuid4()),
        "user_id":              str(uuid.uuid4()),
        "created_at":           datetime.now(timezone.utc).isoformat(),
        "use_case":             _USE_CASE.get(q(1), "mixed"),
        "party_type":           _PARTY_TYPE.get(q(2), "mixed"),
        "daily_budget_tier":    _DAILY_BUDGET.get(q(3), 2),
        "trip_budget_tier":     _TRIP_BUDGET.get(q(4), 2),
        "preferred_tags":       _map_activities(q(5)),
        "exploration_score":    int(q(6) or 3),
        "popularity_weight":    int(q(7) or 3),
        "cuisines_preferences": _map_prefixes(q(8), _CUISINE_PREFIXES),
        "dietary_restrictions": _map_prefixes(q(9), _DIETARY_PREFIXES),
        "travel_mode":          _map_prefixes(q(10), _TRAVEL_MODE_PREFIXES),
        "max_travel_minutes":   _MAX_TRAVEL.get(q(11), "20-40"),
        "itinerary_pace":       pace,
    }


def main(csv_path: str, dry_run: bool = False) -> None:
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader  = csv.DictReader(f)
        headers = list(reader.fieldnames or [])
        rows    = [transform_row(r, headers) for r in reader]

    print(f"Transformed {len(rows)} survey responses.")

    if dry_run:
        import json
        for i, r in enumerate(rows):
            print(f"\n── Row {i+1} ──")
            print(json.dumps(r, indent=2, default=str))
        print("\nDry run — no data written.")
        return

    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
    result   = sb.table("preference").insert(rows).execute()
    inserted = len(result.data) if result.data else 0
    print(f"Inserted {inserted}/{len(rows)} rows into preference table.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m ml.data.seed_survey data/survey_responses.csv [--dry-run]")
        sys.exit(1)
    main(sys.argv[1], dry_run="--dry-run" in sys.argv)
