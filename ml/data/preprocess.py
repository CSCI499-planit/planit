from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional, TypedDict

import pandas as pd

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Stage 1 schema — every data source gets normalised to this before the ML
# pipeline touches it. adding a source field so we can trace where a place
# came from if something looks off in the recommendations.
# ---------------------------------------------------------------------------

class PlaceRecord(TypedDict, total=False):
    place_id:      str
    name:          str
    source:        str            # "geoapify" | "foursquare" | "google" | "lim_poi"
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


# ---------------------------------------------------------------------------
# Stage 2 schemas — user preferences (from the survey) and visit history
# ---------------------------------------------------------------------------

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


class UserVisit(TypedDict, total=False):
    # a single user–place interaction from Google Maps history or in-app activity
    user_id:     str
    place_id:    str
    rating:      Optional[float]   # 1–5; None if not explicitly rated
    visit_count: int                # ≥ 1
    tags:        list[str]          # Stage 1 tags used as the CF signal


# ---------------------------------------------------------------------------
# Foursquare TIST 2015 loaders
# Files: dataset_TIST2015_POIs.txt  (venue_id \t lat \t lon \t category \t country_code)
#        dataset_TIST2015_Checkins.txt  (user_id \t venue_id \t utc_time \t tz_offset)
# These files are large and gitignored — download from the Foursquare TIST 2015 dataset.
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Lim Melbourne POI dataset (POI-Melb.csv / userVisits-Melb-allPOI.csv)
# Used for CF pre-training alongside Foursquare data.
# ---------------------------------------------------------------------------

_LIM_THEME_TO_TAGS: dict[str, list[str]] = {
    "Museum":        ["cultural", "historical", "quick_visit"],
    "Sport":         ["outdoor", "adventurous"],
    "Structure":     ["historical", "scenic"],
    "Park":          ["outdoor", "scenic", "pet_friendly"],
    "Entertainment": ["family_friendly", "quick_visit"],
    "Shopping":      ["shopping", "quick_visit"],
    "Nightlife":     ["nightlife", "food_and_drink"],
    "Food":          ["food_and_drink"],
    "Beach":         ["outdoor", "scenic", "adventurous"],
    "Garden":        ["outdoor", "scenic", "romantic"],
}


def load_lim_poi(poi_path: str | Path) -> list[PlaceRecord]:
    # flexible column detection so the loader works regardless of capitalisation/naming
    df = pd.read_csv(poi_path)
    df.columns = [c.strip() for c in df.columns]
    col = {c.lower(): c for c in df.columns}

    id_col    = col.get("poiid",    col.get("poi_id",   col.get("id",        None)))
    name_col  = col.get("poiname",  col.get("poi_name", col.get("name",      None)))
    theme_col = col.get("poitheme", col.get("theme",    col.get("category",  None)))
    lat_col   = col.get("lat",      col.get("latitude",                      None))
    lon_col   = col.get("lon",      col.get("long",     col.get("longitude", None)))

    records: list[PlaceRecord] = []
    for i, row in df.iterrows():
        pid   = str(row[id_col])   if id_col    else str(i)
        name  = str(row[name_col]) if name_col  else "Unknown"
        theme = str(row[theme_col]).strip() if theme_col else ""
        try:
            lat = float(row[lat_col]) if lat_col else 0.0
            lon = float(row[lon_col]) if lon_col else 0.0
        except (ValueError, TypeError):
            lat, lon = 0.0, 0.0

        tags = _LIM_THEME_TO_TAGS.get(theme) or []
        records.append(PlaceRecord(
            place_id=f"lim_{pid}",
            name=name,
            source="lim_poi",
            latitude=lat,
            longitude=lon,
            categories=[theme.lower()] if theme else [],
            tags=tags or None,
        ))

    logger.info("Loaded %d LIM POI records from %s", len(records), poi_path)
    return records


def load_lim_visits(visits_path: str | Path, poi_records: list[PlaceRecord]) -> list[UserVisit]:
    # attach tags from poi_records by matching place_id so the CF matrix has signal
    df = pd.read_csv(visits_path)
    df.columns = [c.strip() for c in df.columns]
    col = {c.lower(): c for c in df.columns}

    user_col  = col.get("userid",     col.get("user_id",     col.get("uid",   None)))
    poi_col   = col.get("poiid",      col.get("poi_id",      col.get("pid",   None)))
    count_col = col.get("visitcount", col.get("visit_count", col.get("count", None)))

    tag_map: dict[str, list[str]] = {
        p["place_id"]: (p.get("tags") or []) for p in poi_records
    }

    visits: list[UserVisit] = []
    for i, row in df.iterrows():
        uid   = str(row[user_col])  if user_col  else str(i)
        pid   = f"lim_{row[poi_col]}" if poi_col else ""
        count = int(row[count_col]) if count_col else 1

        visits.append(UserVisit(
            user_id=uid,
            place_id=pid,
            visit_count=max(count, 1),
            tags=tag_map.get(pid, []),
        ))

    logger.info("Loaded %d LIM visit records from %s", len(visits), visits_path)
    return visits
