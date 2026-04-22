from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional, TypedDict

import pandas as pd

logger = logging.getLogger(__name__)


class PlaceRecord(TypedDict, total=False):
    place_id:      str
    name:          str
    source:        str            # "geoapify" | "foursquare" | "google"
    latitude:      float
    longitude:     float
    city:          Optional[str]
    state:         Optional[str]
    country:       Optional[str]
    postcode:      Optional[str]
    street:        Optional[str]
    suburb:        Optional[str]
    district:      Optional[str]
    categories:    list[str]      # raw category strings from the source API
    price_level:   Optional[int]  # 1–4
    rating:        Optional[float]
    review_count:  Optional[int]
    hours:         Optional[str]
    attributes:    Optional[dict[str, Any]]   # GoodForKids, DogsAllowed, etc.
    tags:          Optional[list[str]]        # filled in by Stage 1


class UserPreference(TypedDict, total=False):
    # direct mapping of the onboarding survey — backend stores verbatim and
    # passes it straight here, so field names and values must match exactly
    user_id:              str

    # Section 1 — Context
    use_case:             str          # "local" | "daytrip" | "travel" | "mixed"
    party_type:           str          # "solo" | "couple" | "friends" | "family" | "mixed"

    # Section 2 — Budget  (1 = free/budget, 4 = luxury)
    daily_budget_tier:    int
    trip_budget_tier:     Optional[int]   # None for local users ("not applicable")

    # Section 3 — Activities & Interests
    preferred_tags:       list[str]    # subset of the 15 place tags
    exploration_score:    int          # 1–5 (1 = stick to known, 5 = always something new)
    popularity_weight:    int          # 1–5 (1 = ignore reviews, 5 = highly reviewed only)

    # Section 4 — Food & Dining
    cuisine_preferences:  list[str]    # see ALL_CUISINES in user_profiler.py
    dietary_restrictions: list[str]    # see ALL_DIETARY in user_profiler.py

    # Section 5 — Getting Around
    travel_mode:          list[str]    # ["walk"] | ["bike"] | ["transit"] | ["drive"]
    max_travel_minutes:   str          # "< 10" | "10-20" | "20-40" | "> 40"
    itinerary_pace:       str          # "packed" (6/day) | "balanced" (4) | "relaxed" (2)

    # Section 6 — Revisit behaviour
    # False (default): each place appears at most once across all days
    # True: food_and_drink places can repeat across days; landmarks/cultural blocked after first visit
    allow_revisits:       bool


class UserVisit(TypedDict, total=False):
    user_id:     str
    place_id:    str
    rating:      Optional[float]   # 1–5; None if not explicitly rated
    visit_count: int                # ≥ 1
    tags:        list[str]          # Stage 1 tags used as the CF signal


# Foursquare TIST 2015 loaders
# Files: dataset_TIST2015_POIs.txt  (venue_id \t lat \t lon \t category \t country_code)
#        dataset_TIST2015_Checkins.txt  (user_id \t venue_id \t utc_time \t tz_offset)

# maps Foursquare category keywords to our tag vocabulary
_FS_CAT_TO_TAGS: dict[str, list[str]] = {
    # food & drink
    "restaurant":      ["food_and_drink"],
    "café":            ["food_and_drink", "quick_visit"],
    "cafe":            ["food_and_drink", "quick_visit"],
    "coffee":          ["food_and_drink", "quick_visit"],
    "bakery":          ["food_and_drink", "quick_visit"],
    "fast food":       ["food_and_drink", "quick_visit", "budget_friendly"],
    "food truck":      ["food_and_drink", "budget_friendly"],
    "ice cream":       ["food_and_drink", "quick_visit"],
    "dessert":         ["food_and_drink", "quick_visit"],
    "food court":      ["food_and_drink", "quick_visit", "budget_friendly"],
    # nightlife
    "bar":             ["nightlife", "food_and_drink"],
    "pub":             ["nightlife", "food_and_drink"],
    "nightclub":       ["nightlife"],
    "club":            ["nightlife"],
    "lounge":          ["nightlife"],
    "brewery":         ["nightlife", "food_and_drink"],
    "winery":          ["nightlife", "upscale"],
    "jazz":            ["nightlife", "cultural"],
    "music venue":     ["nightlife", "cultural"],
    "casino":          ["nightlife"],
    "cocktail":        ["nightlife", "upscale"],
    # outdoor
    "park":            ["outdoor", "scenic", "pet_friendly"],
    "trail":           ["outdoor", "adventurous"],
    "beach":           ["outdoor", "scenic", "adventurous"],
    "mountain":        ["outdoor", "adventurous", "scenic"],
    "lake":            ["outdoor", "scenic"],
    "river":           ["outdoor", "scenic"],
    "campground":      ["outdoor", "adventurous"],
    "garden":          ["outdoor", "scenic", "romantic"],
    "nature":          ["outdoor", "scenic"],
    "forest":          ["outdoor", "scenic", "adventurous"],
    "ski":             ["outdoor", "adventurous"],
    "surf":            ["outdoor", "adventurous"],
    "dive":            ["outdoor", "adventurous"],
    "harbor":          ["outdoor", "scenic"],
    "pier":            ["outdoor", "scenic"],
    "viewpoint":       ["outdoor", "scenic"],
    "waterfall":       ["outdoor", "scenic", "adventurous"],
    "playground":      ["outdoor", "family_friendly"],
    "recreation":      ["outdoor", "family_friendly"],
    "skate":           ["outdoor", "adventurous"],
    "climbing":        ["outdoor", "adventurous", "wellness"],
    # cultural / historical
    "museum":          ["cultural", "historical"],
    "gallery":         ["cultural"],
    "art gallery":     ["cultural"],
    "theater":         ["cultural"],
    "theatre":         ["cultural"],
    "performing arts": ["cultural"],
    "concert":         ["cultural", "nightlife"],
    "opera":           ["cultural", "upscale"],
    "historic":        ["historical", "scenic"],
    "monument":        ["historical", "scenic"],
    "landmark":        ["historical", "scenic"],
    "castle":          ["historical", "scenic"],
    "palace":          ["historical", "scenic"],
    "ruins":           ["historical", "scenic"],
    "church":          ["historical", "cultural"],
    "cathedral":       ["historical", "cultural"],
    "mosque":          ["historical", "cultural"],
    "temple":          ["historical", "cultural"],
    "memorial":        ["historical", "scenic"],
    # shopping
    "mall":            ["shopping"],
    "market":          ["shopping", "food_and_drink"],
    "boutique":        ["shopping", "upscale"],
    "bookstore":       ["shopping", "quick_visit"],
    "clothing":        ["shopping"],
    "department store": ["shopping"],
    "souvenir":        ["shopping", "quick_visit"],
    "farmers market":  ["shopping", "food_and_drink", "outdoor"],
    "flea market":     ["shopping", "budget_friendly"],
    # wellness
    "gym":             ["wellness"],
    "fitness":         ["wellness"],
    "yoga":            ["wellness"],
    "spa":             ["wellness", "upscale"],
    "pilates":         ["wellness"],
    "pool":            ["wellness", "outdoor"],
    # family / adventure
    "zoo":             ["family_friendly", "outdoor"],
    "aquarium":        ["family_friendly", "cultural"],
    "amusement":       ["family_friendly", "adventurous"],
    "bowling":         ["family_friendly", "quick_visit"],
    "arcade":          ["family_friendly", "quick_visit"],
    "theme park":      ["family_friendly", "adventurous"],
    "water park":      ["family_friendly", "adventurous", "outdoor"],
    # upscale
    "resort":          ["upscale"],
    "fine dining":     ["upscale", "food_and_drink"],
    "steakhouse":      ["upscale", "food_and_drink"],
}

# categories to skip — not travel destinations, just utilities
_FS_CAT_SKIP: set[str] = {
    "airport", "train station", "bus station", "subway", "transit",
    "college", "university", "school", "hospital", "clinic", "doctor",
    "office", "government", "dmv", "post office", "bank", "atm",
    "gas station", "automotive", "car wash", "laundry", "storage",
    "residential", "building", "home",
}


def _foursquare_cat_to_tags(category: str) -> list[str]:
    cat = category.strip().lower()
    if any(skip in cat for skip in _FS_CAT_SKIP):
        return []
    tags: set[str] = set()
    for keyword, mapped in _FS_CAT_TO_TAGS.items():
        if keyword in cat:
            tags.update(mapped)
    return list(tags)


def load_foursquare_pois(poi_path: str | Path) -> list[PlaceRecord]:
    # TSV: venue_id  latitude  longitude  category  country_code  (no header)
    df = pd.read_csv(
        poi_path, sep="\t", header=None,
        names=["venue_id", "latitude", "longitude", "category", "country_code"],
        dtype={"venue_id": str, "country_code": str},
    )
    logger.info("Read %d Foursquare venues from %s", len(df), poi_path)

    records: list[PlaceRecord] = []
    for _, row in df.iterrows():
        cat  = str(row.get("category") or "")
        tags = _foursquare_cat_to_tags(cat)
        if not tags:
            continue
        try:
            lat = float(row["latitude"])
            lon = float(row["longitude"])
        except (ValueError, TypeError):
            lat, lon = 0.0, 0.0

        records.append(PlaceRecord(
            place_id=str(row["venue_id"]),
            source="foursquare",
            latitude=lat,
            longitude=lon,
            country=str(row.get("country_code") or ""),
            categories=[cat.lower()],
            tags=tags,
        ))

    logger.info("Kept %d Foursquare venues after tag filtering", len(records))
    return records


def load_foursquare_checkins(
    checkin_path:  str | Path,
    venue_tag_map: dict[str, list[str]],
    min_checkins:  int = 5,
    max_users:     int | None = 50_000,
) -> list[UserVisit]:
    # only load venues that made it through tag filtering so we don't carry
    # utility places (banks, transit stops, etc.) into the CF matrix
    logger.info("Reading Foursquare check-ins from %s …", checkin_path)
    chunks = []
    for chunk in pd.read_csv(
        checkin_path, sep="\t", header=None,
        names=["user_id", "venue_id", "utc_time", "tz_offset"],
        usecols=[0, 1],
        chunksize=500_000,
        dtype={"user_id": str, "venue_id": str},
    ):
        sub = chunk[chunk["venue_id"].isin(venue_tag_map)]
        chunks.append(sub)

    df = pd.concat(chunks, ignore_index=True)
    logger.info("Loaded %d relevant check-ins", len(df))

    # drop users who barely used Foursquare — their signal is too sparse to be useful
    counts       = df["user_id"].value_counts()
    active_users = counts[counts >= min_checkins].index
    df           = df[df["user_id"].isin(active_users)]

    if max_users is not None and len(active_users) > max_users:
        sampled = pd.Series(active_users).sample(max_users, random_state=42)
        df      = df[df["user_id"].isin(sampled)]
        logger.info("Sampled %d / %d qualifying users", max_users, len(active_users))

    # aggregate to one row per (user, venue) — visit_count captures repeat visits
    grouped = (
        df.groupby(["user_id", "venue_id"])
        .size()
        .reset_index(name="visit_count")
    )

    visits: list[UserVisit] = []
    for _, row in grouped.iterrows():
        vid  = str(row["venue_id"])
        tags = venue_tag_map.get(vid, [])
        if not tags:
            continue
        visits.append(UserVisit(
            user_id=str(row["user_id"]),
            place_id=vid,
            visit_count=int(row["visit_count"]),
            tags=tags,
        ))

    logger.info(
        "Built %d user-venue visit pairs (%d unique users)",
        len(visits), grouped["user_id"].nunique(),
    )
    return visits
