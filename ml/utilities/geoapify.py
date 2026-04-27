# Geoapify API calls + response parsing.
# Everything gets normalised to the shared PlaceRecord schema before
# entering the ML pipeline this is the only place Geoapify JSON is touched.

from __future__ import annotations

import os
import logging
from difflib import SequenceMatcher
from typing import Any

import httpx

from ml.data.preprocess import PlaceRecord

logger = logging.getLogger(__name__)


def _api_key() -> str:
    return os.getenv("GEOAPIFY_KEY", "")


# Geoapify place categories that map well to our tag vocabulary
FETCH_CATEGORIES = [
    "catering.restaurant", "catering.cafe", "catering.bar",
    "entertainment.museum",
    "leisure.park",
    "tourism.attraction", "tourism.sights",
    "sport.fitness",
    "commercial.shopping_mall", "commercial.marketplace",
]


def geocode_location(location: str) -> tuple[float, float]:
    # accepts cities, neighbourhoods, hotel names, landmarks, addresses
    resp = httpx.get(
        "https://api.geoapify.com/v1/geocode/search",
        params={"text": location, "limit": 1, "apiKey": _api_key()},
        timeout=10.0,
    )
    resp.raise_for_status()
    features = resp.json().get("features", [])
    if not features:
        raise ValueError(f"Location not found: {location!r}")
    coords = features[0]["geometry"]["coordinates"]
    return float(coords[1]), float(coords[0])  # lat, lon


def fetch_places(lat: float, lon: float, radius_m: int = 5000, limit: int = 50) -> list[PlaceRecord]:
    url = (
        f"https://api.geoapify.com/v2/places"
        f"?categories={','.join(FETCH_CATEGORIES)}"
        f"&filter=circle:{lon},{lat},{radius_m}"
        f"&limit={limit}"
        f"&apiKey={_api_key()}"
    )
    resp = httpx.get(url, timeout=15.0)
    resp.raise_for_status()
    return parse_geoapify_response(resp.json())


def fetch_places_for_location(location: str, radius_m: int = 5000, limit: int = 50) -> list[PlaceRecord]:
    from ml.utilities.osm import fetch_osm_features, enrich_places_with_osm
    lat, lon = geocode_location(location)
    logger.info("Geocoded %r → (%.4f, %.4f)", location, lat, lon)
    places = fetch_places(lat, lon, radius_m=radius_m, limit=limit)
    osm_features = fetch_osm_features(lat, lon, radius_m=radius_m)
    places = enrich_places_with_osm(places, osm_features)
    places = _deduplicate_by_name(places)
    logger.info("Fetched %d places for %r (after dedup)",
                len(places), location)
    return places


_DEDUP_SIMILARITY_THRESHOLD = 0.85   # Levenshtein-equivalent via SequenceMatcher


def _deduplicate_by_name(places: list[PlaceRecord]) -> list[PlaceRecord]:
    # Keeps only the first occurrence of each (fuzzy) name.
    # Exact match first, then 85 % similarity check — catches chain variants like
    # "Tully's Coffee Shibuya" vs "Tully's Coffee Harajuku" without collapsing
    # genuinely distinct venues with short similar names (e.g. "Bar A" vs "Bar B").
    canonical: list[str] = []
    out: list[PlaceRecord] = []
    for p in places:
        key = p.get("name", "").strip().lower()
        if not key:
            continue
        if any(
            SequenceMatcher(None, key, c).ratio(
            ) >= _DEDUP_SIMILARITY_THRESHOLD
            for c in canonical
        ):
            continue
        canonical.append(key)
        out.append(p)
    return out


def parse_geoapify_feature(feature: dict[str, Any]) -> PlaceRecord | None:
    # returns None if the feature is missing a name or coordinates — skip those
    props = feature.get("properties", {})
    geom = feature.get("geometry", {})

    name = props.get("name", "").strip()
    if not name:
        return None

    coords = geom.get("coordinates")
    if not coords or len(coords) < 2:
        return None

    lon, lat = coords[0], coords[1]

    categories: list[str] = [c.lower()
                             for c in (props.get("categories") or [])]

    # pull useful sub-fields from Geoapify's nested objects into our flat attributes dict
    attrs: dict[str, Any] = {}
    if props.get("catering"):
        c = props["catering"]
        if c.get("outdoor_seating"):
            attrs["OutdoorSeating"] = c["outdoor_seating"]
        if c.get("cuisine"):
            attrs["cuisine"] = c["cuisine"]
        if c.get("diet"):
            attrs["diet"] = c["diet"]
    if props.get("facilities"):
        f = props["facilities"]
        if f.get("dogs"):
            attrs["DogsAllowed"] = f["dogs"]
        if f.get("wheelchair"):
            attrs["WheelchairAccessible"] = f["wheelchair"]
    if props.get("fee"):
        attrs["HasFee"] = props["fee"]

    return {
        "place_id":      props.get("place_id", ""),
        "name":          name,
        "source":        "geoapify",
        "latitude":      float(lat),
        "longitude":     float(lon),
        "city":          props.get("city"),
        "state":         props.get("state"),
        "country":       props.get("country"),
        "postcode":      str(props.get("postcode", "")) or None,
        "street":        props.get("street"),
        "suburb":        props.get("suburb"),
        "district":      props.get("district"),
        "categories":    categories,
        "hours":         props.get("opening_hours"),
        "attributes":    attrs if attrs else None,
        # Geoapify free tier doesn't return rating or price data
        "price_level":   None,
        "rating":        None,
        "review_count":  None,
    }


def normalize_db_place(row: dict[str, Any]) -> PlaceRecord:
    # maps a Supabase 'place' table row → PlaceRecord (id→place_id, lat/lon passthrough)
    return {
        "place_id":   str(row.get("id", "")),
        "name":       row.get("name", ""),
        "source":     "supabase",
        "latitude":   float(row.get("lat") or 0.0),
        "longitude":  float(row.get("lon") or 0.0),
        "city":       row.get("city"),
        "state":      row.get("state"),
        "country":    row.get("country"),
        "postcode":   row.get("postcode"),
        "street":     row.get("street"),
        "suburb":     row.get("suburb"),
        "district":   row.get("district"),
        "categories": list(row.get("categories") or []),
        "hours":      row.get("hours"),
        "price_level":  None,
        "rating":       None,
        "review_count": None,
        "attributes":   None,
        "tags":         None,
    }


def parse_geoapify_response(response: dict[str, Any]) -> list[PlaceRecord]:
    # converts a full FeatureCollection response into a list of PlaceRecords
    records: list[PlaceRecord] = []
    skipped = 0
    for feat in response.get("features", []):
        record = parse_geoapify_feature(feat)
        if record is not None:
            records.append(record)
        else:
            skipped += 1
    if skipped:
        logger.debug("Skipped %d features (missing name or coords)", skipped)
    return records
