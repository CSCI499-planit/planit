from __future__ import annotations

import ast
import logging
import re
from typing import Any

from ml.data.preprocess import PlaceRecord

logger = logging.getLogger(__name__)


def _parse_place_attributes(attrs: dict | None) -> dict[str, Any]:
    # Geoapify sometimes returns nested dicts as stringified Python dicts
    # e.g. "{'free': True, 'paid': False}" — flatten to "WiFi.free": True
    if not attrs:
        return {}
    flat: dict[str, Any] = {}
    for key, value in attrs.items():
        if isinstance(value, str) and value.startswith("{"):
            try:
                sub = ast.literal_eval(value)
                if isinstance(sub, dict):
                    for subkey, subval in sub.items():
                        flat[f"{key}.{subkey}"] = subval
                    continue
            except (ValueError, SyntaxError):
                pass
        flat[key] = value
    return flat


def _parse_price_level(attrs: dict | None) -> int | None:
    # pull price level from the Yelp-style RestaurantsPriceRange2 attribute
    if not attrs:
        return None
    raw = attrs.get("RestaurantsPriceRange2")
    if raw is None:
        return None
    try:
        level = int(raw)
        return level if 1 <= level <= 4 else None
    except (TypeError, ValueError):
        return None


def _parse_opening_hours_features(hours_str: str | None) -> dict[str, bool]:
    # derive boolean flags from an OSM hours string — used in both tagging and scoring
    features = {
        "opens_late":     False,   # closes at or after 22:00
        "opens_early":    False,   # opens at or before 08:00
        "open_weekend":   False,
        "is_always_open": False,   # 24/7
    }
    if not hours_str:
        return features

    h = hours_str.lower()

    if "24/7" in h or ("00:00-24:00" in h and "mo-su" in h):
        return {k: True for k in features}

    features["open_weekend"] = any(t in h for t in ("sa", "su", "sat", "sun", "ph"))

    for t in re.findall(r"-(\d{2}):\d{2}", h):
        if int(t) >= 22 or int(t) < 4:
            features["opens_late"] = True
            break

    for t in re.findall(r"(?:^|[;\s])(\d{2}):\d{2}-", h):
        if int(t) <= 8:
            features["opens_early"] = True
            break

    return features


# 15 contextual tags — these are the vocabulary for everything downstream
PLACE_TAGS: list[str] = [
    "family_friendly",  # good for kids / families
    "romantic",         # date spots, intimate settings
    "adventurous",      # hiking, extreme sports, outdoor challenges
    "budget_friendly",  # affordable / free
    "upscale",          # luxury, fine dining, premium
    "cultural",         # museums, galleries, theatres, art
    "outdoor",          # parks, beaches, nature, gardens
    "nightlife",        # bars, clubs, late-night venues
    "food_and_drink",   # restaurants, cafes, food markets
    "shopping",         # malls, boutiques, markets
    "wellness",         # spas, fitness, yoga
    "historical",       # landmarks, heritage, monuments
    "scenic",           # viewpoints, natural beauty
    "pet_friendly",     # dog-friendly venues
    "quick_visit",      # typically under 1 hour
]




def rule_based_labels(place: PlaceRecord) -> dict[str, int]:
    labels     = {tag: 0 for tag in PLACE_TAGS}
    categories = [c.lower() for c in (place.get("categories") or [])]
    attrs      = _parse_place_attributes(place.get("attributes"))
    price      = place.get("price_level") or _parse_price_level(place.get("attributes"))
    rating     = place.get("rating") or 0.0
    hours_feat = _parse_opening_hours_features(place.get("hours"))

    def _has_cat(*patterns: str) -> bool:
        return any(any(p in cat for cat in categories) for p in patterns)

    def _bool_attr(key: str) -> bool:
        val = attrs.get(key)
        return str(val).lower() in ("true", "1", "yes") if val is not None else False

    if _has_cat("catering", "restaurants", "food", "coffee"):
        labels["food_and_drink"] = 1

    if _has_cat("catering.bar", "catering.pub", "catering.nightclub", "nightlife", "bars"):
        labels["nightlife"] = 1
    if hours_feat["opens_late"] and labels["food_and_drink"]:
        labels["nightlife"] = 1

    if _has_cat("leisure", "natural.", "sport", "parks", "hiking", "beaches", "active life"):
        labels["outdoor"] = 1
    if _bool_attr("OutdoorSeating"):
        labels["outdoor"] = 1

    if _has_cat("entertainment.museum", "entertainment.art", "entertainment.theatre",
                "entertainment.cinema", "tourism.museum", "museums",
                "arts & entertainment", "landmarks"):
        labels["cultural"] = 1

    if _has_cat("tourism.sights", "tourism.museum", "landmarks", "historical"):
        labels["historical"] = 1
    if attrs.get("OSMHistoric"):
        labels["historical"] = 1
        labels["scenic"] = 1   # historic sites are almost always scenic

    if _has_cat("leisure.playground", "entertainment.theme_park",
                "entertainment.zoo", "entertainment.aquarium"):
        labels["family_friendly"] = 1
    if _bool_attr("GoodForKids") or _bool_attr("OSMPlayground"):
        labels["family_friendly"] = 1

    if _has_cat("commercial", "shopping"):
        labels["shopping"] = 1

    if _has_cat("sport.fitness", "healthcare.alternative", "spas", "fitness"):
        labels["wellness"] = 1

    if _has_cat("natural.beach", "natural.mountain", "natural.forest",
                "leisure.garden", "tourism.attraction", "tourism.sights", "landmarks"):
        labels["scenic"] = 1
    if _bool_attr("OSMViewpoint") or _bool_attr("OSMGarden"):
        labels["scenic"] = 1
    osm_natural = str(attrs.get("OSMNatural", "")).lower()
    if osm_natural in ("peak", "waterfall", "cliff", "beach", "wood", "forest"):
        labels["scenic"] = 1
        labels["outdoor"] = 1
        if osm_natural in ("peak", "waterfall", "cliff"):
            labels["adventurous"] = 1

    if _has_cat("sport.hiking", "sport.climbing", "sport.skiing", "sport.cycling",
                "natural.mountain", "natural.", "active life", "hiking", "climbing"):
        labels["adventurous"] = 1
    osm_sport = str(attrs.get("OSMSport", "")).lower()
    if any(s in osm_sport for s in ("climbing", "hiking", "skiing", "surfing", "mountaineering")):
        labels["adventurous"] = 1
        labels["outdoor"] = 1

    if _bool_attr("DogsAllowed"):
        labels["pet_friendly"] = 1

    if _bool_attr("Romantic"):
        labels["romantic"] = 1
    # gardens with high price/rating are inherently romantic — restaurants are not
    if (_has_cat("leisure.garden") or _bool_attr("OSMGarden")) \
            and price and price >= 3 and rating >= 4.0:
        labels["romantic"] = 1

    if price == 1 or _has_cat("catering.fast_food", "commercial.supermarket", "leisure.playground"):
        labels["budget_friendly"] = 1
    if attrs.get("FeeRequired") is False:
        labels["budget_friendly"] = 1

    if price and price >= 3:
        labels["upscale"] = 1
    if _has_cat("accommodation.hotel") and rating >= 4.0:
        labels["upscale"] = 1

    if _has_cat("catering.cafe", "catering.fast_food", "catering.ice_cream",
                "commercial.supermarket", "tourism.information"):
        labels["quick_visit"] = 1

    return labels


