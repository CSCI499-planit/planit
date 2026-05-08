from __future__ import annotations

import logging
import math
from typing import Any

import httpx

from ml.data.preprocess import PlaceRecord

logger = logging.getLogger(__name__)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# one query per fetch. pulls features whose tags to fill gaps in Geoapify's categories
_QUERY = """
[out:json][timeout:30];
(
  node["historic"](around:{r},{lat},{lon});
  way["historic"](around:{r},{lat},{lon});
  node["tourism"="viewpoint"](around:{r},{lat},{lon});
  node["leisure"="garden"](around:{r},{lat},{lon});
  way["leisure"="garden"](around:{r},{lat},{lon});
  node["natural"~"^(peak|waterfall|cliff|beach|wood|forest)$"](around:{r},{lat},{lon});
  way["natural"~"^(peak|waterfall|cliff|beach|wood|forest)$"](around:{r},{lat},{lon});
  node["sport"~"^(climbing|hiking|skiing|surfing|cycling|mountaineering)$"](around:{r},{lat},{lon});
  node["amenity"="playground"](around:{r},{lat},{lon});
  node["dog"~"^(yes|leashed)$"](around:{r},{lat},{lon});
  way["dog"~"^(yes|leashed)$"](around:{r},{lat},{lon});
  node["pets_allowed"="yes"](around:{r},{lat},{lon});
  node["child_friendly"="yes"](around:{r},{lat},{lon});
  node["fee"="no"]["amenity"](around:{r},{lat},{lon});
  way["fee"="no"]["amenity"](around:{r},{lat},{lon});
  node["outdoor_seating"="yes"](around:{r},{lat},{lon});
);
out center;
"""


def fetch_osm_features(lat: float, lon: float, radius_m: int = 5000) -> list[dict]:
    query_data = {"data": _QUERY.format(lat=lat, lon=lon, r=radius_m)}
    headers    = {"User-Agent": "PlanIt/1.0 (travel-recommendation-app; contact@planit.app)"}
    for attempt in range(2):
        try:
            resp = httpx.post(OVERPASS_URL, data=query_data, headers=headers, timeout=30.0)
            resp.raise_for_status()
            elements = resp.json().get("elements", [])
            logger.info("Fetched %d OSM features near (%.4f, %.4f)", len(elements), lat, lon)
            return elements
        except Exception as e:
            if attempt == 0:
                logger.warning("Overpass attempt 1 failed (%s) — retrying", e)
            else:
                logger.warning("Overpass attempt 2 failed (%s) — skipping OSM enrichment", e)
    return []


def _element_latlon(el: dict) -> tuple[float, float] | None:
    if el.get("type") == "node":
        lat, lon = el.get("lat"), el.get("lon")
        if lat is not None and lon is not None:
            return float(lat), float(lon)
    center = el.get("center")
    if center:
        return float(center["lat"]), float(center["lon"])
    return None


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6_371_000.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _osm_tags_to_attrs(tags: dict[str, str]) -> dict[str, Any]:
    attrs: dict[str, Any] = {}

    if tags.get("dog") in ("yes", "leashed") or tags.get("pets_allowed") == "yes":
        attrs["DogsAllowed"] = True

    if tags.get("child_friendly") == "yes":
        attrs["GoodForKids"] = True

    if tags.get("outdoor_seating") == "yes":
        attrs["OutdoorSeating"] = True

    if tags.get("fee") == "no":
        attrs["FeeRequired"] = False

    historic = tags.get("historic")
    if historic:
        attrs["OSMHistoric"] = historic

    if tags.get("tourism") == "viewpoint":
        attrs["OSMViewpoint"] = True

    natural = tags.get("natural")
    if natural:
        attrs["OSMNatural"] = natural

    sport = tags.get("sport")
    if sport:
        attrs["OSMSport"] = sport

    if tags.get("amenity") == "playground":
        attrs["OSMPlayground"] = True

    leisure = tags.get("leisure")
    if leisure == "garden":
        attrs["OSMGarden"] = True

    return attrs


def enrich_places_with_osm(
    places:       list[PlaceRecord],
    osm_features: list[dict],
    max_dist_m:   float = 150.0,
) -> list[PlaceRecord]:
    # build flat list of (lat, lon, attrs)
    osm_points: list[tuple[float, float, dict]] = []
    for el in osm_features:
        ll = _element_latlon(el)
        if ll is None:
            continue
        attrs = _osm_tags_to_attrs(el.get("tags", {}))
        if attrs:
            osm_points.append((ll[0], ll[1], attrs))

    # categories that indicate a food/drink venue, fee=no from a nearby park or museum
    _FOOD_CATS = {"catering", "restaurant", "food", "coffee", "bar", "pub"}

    enriched: list[PlaceRecord] = []
    for place in places:
        plat = place.get("latitude", 0.0)
        plon = place.get("longitude", 0.0)
        cats = {c.lower() for c in (place.get("categories") or [])}
        is_food = any(f in cat for f in _FOOD_CATS for cat in cats)

        merged = dict(place.get("attributes") or {})
        for olat, olon, oattrs in osm_points:
            if _haversine_m(plat, plon, olat, olon) <= max_dist_m:
                attrs_to_add = dict(oattrs)
                if is_food:
                    attrs_to_add.pop("FeeRequired", None)
                merged.update(attrs_to_add)

        enriched.append({**place, "attributes": merged or None})

    n_enriched = sum(1 for p, e in zip(places, enriched)
                     if (e.get("attributes") or {}) != (p.get("attributes") or {}))
    logger.info("OSM enriched %d / %d places", n_enriched, len(places))
    return enriched
