# Geoapify API calls + response parsing.
# Everything gets normalised to the shared PlaceRecord schema before
# entering the ML pipeline this is the only place Geoapify JSON is touched.

from __future__ import annotations

import math
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
    geo = _geocode_full(location)
    return geo["lat"], geo["lon"]


_MIN_BBOX_DIAGONAL_M = 300   # smaller → point geocode, fall back to radius
_MAX_OSM_RADIUS_M    = 5_000 # Overpass cap to avoid timeouts on large bboxes


def _bbox_diagonal_m(bbox: list[float]) -> float:
    """Return the diagonal of a [W, S, E, N] bbox in metres."""
    west, south, east, north = bbox
    lat_m = (north - south) * 111_320
    lon_m = (east - west) * 111_320 * math.cos(math.radians((south + north) / 2))
    return math.hypot(lat_m, lon_m)


def _geocode_full(location: str) -> dict:
    """Geocode and return lat, lon, bbox, and bbox_diagonal_m.

    bbox is [west, south, east, north] (min_lon, min_lat, max_lon, max_lat).
    bbox is set to None when the geocoded result is a point rather than an
    area (diagonal < _MIN_BBOX_DIAGONAL_M), so callers fall back to radius.
    Returns {"lat", "lon", "bbox", "bbox_diagonal_m"}.
    """
    resp = httpx.get(
        "https://api.geoapify.com/v1/geocode/search",
        params={"text": location, "limit": 1, "apiKey": _api_key()},
        timeout=10.0,
    )
    resp.raise_for_status()
    features = resp.json().get("features", [])
    if not features:
        raise ValueError(f"Location not found: {location!r}")

    feat = features[0]
    coords = feat["geometry"]["coordinates"]
    lat, lon = float(coords[1]), float(coords[0])

    # Geoapify returns bbox in properties.bbox as {lon1, lat1, lon2, lat2}
    # Fall back to GeoJSON top-level bbox array if present
    bbox = None
    props = feat.get("properties", {})
    raw = props.get("bbox")
    if isinstance(raw, dict) and all(k in raw for k in ("lon1", "lat1", "lon2", "lat2")):
        bbox = [raw["lon1"], raw["lat1"], raw["lon2"], raw["lat2"]]
    elif isinstance(feat.get("bbox"), list) and len(feat["bbox"]) == 4:
        bbox = feat["bbox"]

    diagonal_m = _bbox_diagonal_m(bbox) if bbox else 0.0
    if diagonal_m < _MIN_BBOX_DIAGONAL_M:
        # Point geocode (lake, address, landmark) — bbox is useless for place search
        bbox = None
        diagonal_m = 0.0

    return {"lat": lat, "lon": lon, "bbox": bbox, "bbox_diagonal_m": diagonal_m}


def geocode_candidates(query: str, limit: int = 5) -> list[dict]:
    """Return up to `limit` ranked location matches for a free-text query.

    Each entry: {"display": str, "lat": float, "lon": float}
    Returns an empty list when nothing is found (never raises on empty results).
    """
    resp = httpx.get(
        "https://api.geoapify.com/v1/geocode/search",
        params={"text": query, "limit": limit, "apiKey": _api_key()},
        timeout=10.0,
    )
    resp.raise_for_status()
    results = []
    for feat in resp.json().get("features", []):
        props = feat.get("properties", {})
        coords = feat.get("geometry", {}).get("coordinates", [])
        if len(coords) < 2:
            continue
        display = (
            props.get("formatted")
            or ", ".join(filter(None, [
                props.get("name"), props.get("city"),
                props.get("state"), props.get("country"),
            ]))
            or query
        )
        results.append({
            "display": display,
            "lat":     float(coords[1]),
            "lon":     float(coords[0]),
        })
    return results


def fetch_places(
    lat: float,
    lon: float,
    radius_m: int = 5000,
    limit: int = 50,
    bbox: list[float] | None = None,
) -> list[PlaceRecord]:
    # Prefer bbox rect filter (exact place boundary) over circle when available
    if bbox:
        geo_filter = f"rect:{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}"
    else:
        geo_filter = f"circle:{lon},{lat},{radius_m}"

    url = (
        f"https://api.geoapify.com/v2/places"
        f"?categories={','.join(FETCH_CATEGORIES)}"
        f"&filter={geo_filter}"
        f"&limit={limit}"
        f"&apiKey={_api_key()}"
    )
    resp = httpx.get(url, timeout=30.0)
    resp.raise_for_status()
    return parse_geoapify_response(resp.json())


def fetch_places_enriched(
    lat: float,
    lon: float,
    radius_m: int = 5000,
    limit: int = 50,
    bbox: list[float] | None = None,
    bbox_diagonal_m: float = 0.0,
) -> list[PlaceRecord]:
    """Like fetch_places() but runs OSM enrichment in parallel for better tagging."""
    from concurrent.futures import ThreadPoolExecutor
    from ml.utilities.osm import fetch_osm_features, enrich_places_with_osm

    # When bbox covers a large area (city-scale), use half the diagonal as the
    # OSM radius so features overlap with the places Geoapify returned, capped
    # to avoid Overpass timeouts.
    if bbox_diagonal_m > 0:
        osm_radius = min(int(bbox_diagonal_m / 2), _MAX_OSM_RADIUS_M)
    else:
        osm_radius = radius_m

    with ThreadPoolExecutor(max_workers=2) as pool:
        geo_future = pool.submit(fetch_places, lat, lon, radius_m=radius_m, limit=limit, bbox=bbox)
        osm_future = pool.submit(fetch_osm_features, lat, lon, radius_m=osm_radius)

        places = geo_future.result()
        try:
            osm_features = osm_future.result()
            places = enrich_places_with_osm(places, osm_features)
        except Exception as e:
            logger.warning("OSM enrichment failed (skipping): %s", e)

    return _deduplicate_by_name(places)


def fetch_places_for_location(location: str, radius_m: int = 5000, limit: int = 50) -> list[PlaceRecord]:
    geo = _geocode_full(location)
    lat, lon, bbox, diag = geo["lat"], geo["lon"], geo["bbox"], geo["bbox_diagonal_m"]
    if bbox:
        logger.info("Geocoded %r → (%.4f, %.4f) bbox diagonal %.0fm", location, lat, lon, diag)
    else:
        logger.info("Geocoded %r → (%.4f, %.4f) — point geocode, using radius %dm", location, lat, lon, radius_m)
    places = fetch_places_enriched(lat, lon, radius_m=radius_m, limit=limit, bbox=bbox, bbox_diagonal_m=diag)
    logger.info("Fetched %d places for %r (after dedup)", len(places), location)
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
    # returns None if the feature is missing a name or coordinates
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

    # Build a display-ready address from Geoapify's pre-formatted string.
    # Falls back to manual concatenation when formatted is absent.
    address: str | None = props.get("formatted") or None
    if not address:
        parts = filter(None, [
            props.get("street"), props.get("city"),
            props.get("postcode"), props.get("country"),
        ])
        address = ", ".join(parts) or None

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
        "address":       address,
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
