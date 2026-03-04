from __future__ import annotations

import ast
import logging
import math
import re
from pathlib import Path
from typing import Any, Literal

import numpy as np

from ml.data.preprocess import PlaceRecord

logger = logging.getLogger(__name__)


# Yelp attributes can contain stringified dicts like "{'free': True, 'paid': False}"
# Flattens them to "WiFi.free": True so feature extraction can read them directly
def _parse_yelp_attributes(attrs: dict | None) -> dict[str, Any]:
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


# Pulls price level from Yelp's RestaurantsPriceRange2 attribute
def _parse_yelp_price_level(attrs: dict | None) -> int | None:
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


# Derives boolean flags from an OSM / Yelp hours string
def _parse_opening_hours_features(hours_str: str | None) -> dict[str, bool]:
    features = {
        "opens_late":     False,   # closes at or after 22:00
        "opens_early":    False,   # opens at or before 08:00
        "open_weekend":   False,   # open Sat or Sun
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


# 15 contextual tags assigned to each place
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

TAG_INDEX: dict[str, int] = {tag: i for i, tag in enumerate(PLACE_TAGS)}


# ---------------------------------------------------------------------------
# Feature extraction
# ---------------------------------------------------------------------------

class PlaceFeatureExtractor:
    # 23 features total: 9 category flags, 3 numeric, 7 attribute flags, 4 hours flags
    FEATURE_NAMES: list[str] = [
        "cat_food_drink", "cat_outdoor", "cat_cultural", "cat_nightlife",
        "cat_shopping", "cat_wellness", "cat_tourism", "cat_sport", "cat_nature",
        "price_level", "rating", "review_count_log",
        "attr_kids", "attr_dogs", "attr_outdoor_seating",
        "attr_romantic", "attr_groups", "attr_late_night", "attr_alcohol",
        "hours_late", "hours_early", "hours_weekend", "hours_always",
    ]

    # which category substrings count toward each category flag
    # works for both Geoapify ("catering.restaurant") and Yelp ("restaurants")
    _CAT_GROUPS: dict[str, list[str]] = {
        "cat_food_drink": ["catering", "restaurants", "food", "coffee"],
        "cat_outdoor":    ["leisure", "natural", "beaches", "parks", "hiking"],
        "cat_cultural":   ["entertainment.museum", "entertainment.art", "entertainment.theatre",
                           "entertainment.cinema", "tourism.museum", "museums",
                           "arts & entertainment"],
        "cat_nightlife":  ["nightlife", "catering.bar", "catering.pub", "catering.nightclub", "bars"],
        "cat_shopping":   ["commercial", "shopping"],
        "cat_wellness":   ["sport.fitness", "healthcare", "spas", "fitness"],
        "cat_tourism":    ["tourism.attraction", "tourism.sights", "tours", "landmarks"],
        "cat_sport":      ["sport.", "active life", "hiking", "cycling", "climbing"],
        "cat_nature":     ["natural.", "beaches", "parks", "hiking", "forest"],
    }

    def extract(self, place: PlaceRecord) -> np.ndarray:
        categories = [c.lower() for c in (place.get("categories") or [])]
        attrs      = _parse_yelp_attributes(place.get("attributes"))
        hours_feat = _parse_opening_hours_features(place.get("hours"))

        vec: list[float] = []

        # category flags — 1 if any category string matches any pattern in the group
        for patterns in self._CAT_GROUPS.values():
            flag = any(any(pat in cat for cat in categories) for pat in patterns)
            vec.append(float(flag))

        # price (0 = unknown), rating (0 = unknown), log review count
        price = place.get("price_level") or _parse_yelp_price_level(place.get("attributes"))
        vec.append(float(price) if price is not None else 0.0)
        rating = place.get("rating")
        vec.append(float(rating) if rating is not None else 0.0)
        rc = place.get("review_count")
        vec.append(math.log1p(rc) if rc is not None else 0.0)

        # Yelp attribute flags — keys match Yelp's attribute naming
        def _bool(key: str) -> float:
            val = attrs.get(key)
            return 1.0 if val is not None and str(val).lower() in ("true", "1", "yes") else 0.0

        vec.append(_bool("GoodForKids"))
        vec.append(_bool("DogsAllowed"))
        vec.append(_bool("OutdoorSeating"))
        vec.append(_bool("Romantic"))
        vec.append(_bool("RestaurantsGoodForGroups"))
        vec.append(_bool("GoodForMeal.latenight"))

        # alcohol: 0 = none, 0.5 = beer/wine, 1.0 = full bar
        alcohol = str(attrs.get("Alcohol", "")).lower()
        if "full_bar" in alcohol:
            vec.append(1.0)
        elif "beer" in alcohol or "wine" in alcohol:
            vec.append(0.5)
        else:
            vec.append(0.0)

        vec.append(float(hours_feat["opens_late"]))
        vec.append(float(hours_feat["opens_early"]))
        vec.append(float(hours_feat["open_weekend"]))
        vec.append(float(hours_feat["is_always_open"]))

        return np.array(vec, dtype=np.float32)

    def extract_batch(self, places: list[PlaceRecord]) -> np.ndarray:
        return np.stack([self.extract(p) for p in places])

    def get_feature_names(self) -> list[str]:
        return self.FEATURE_NAMES


# ---------------------------------------------------------------------------
# Rule-based labelling — generates training labels from categories + attributes
# Used to bootstrap training before human-labelled data is available
# ---------------------------------------------------------------------------

def rule_based_labels(place: PlaceRecord) -> dict[str, int]:
    labels: dict[str, int] = {tag: 0 for tag in PLACE_TAGS}
    categories = [c.lower() for c in (place.get("categories") or [])]
    attrs      = _parse_yelp_attributes(place.get("attributes"))
    price      = place.get("price_level") or _parse_yelp_price_level(place.get("attributes"))
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

    if _has_cat("leisure.playground", "entertainment.theme_park",
                "entertainment.zoo", "entertainment.aquarium"):
        labels["family_friendly"] = 1
    if _bool_attr("GoodForKids"):
        labels["family_friendly"] = 1

    if _has_cat("commercial", "shopping"):
        labels["shopping"] = 1

    if _has_cat("sport.fitness", "healthcare.alternative", "spas", "fitness"):
        labels["wellness"] = 1

    if _has_cat("natural.beach", "natural.mountain", "natural.forest",
                "leisure.garden", "tourism.attraction", "tourism.sights", "landmarks"):
        labels["scenic"] = 1

    if _has_cat("sport.hiking", "sport.climbing", "sport.skiing", "sport.cycling",
                "natural.mountain", "natural.", "active life", "hiking", "climbing"):
        labels["adventurous"] = 1

    if _bool_attr("DogsAllowed"):
        labels["pet_friendly"] = 1

    if _bool_attr("Romantic"):
        labels["romantic"] = 1
    if _has_cat("leisure.garden", "catering.restaurant") and price and price >= 3 and rating >= 4.0:
        labels["romantic"] = 1

    if price == 1 or _has_cat("catering.fast_food", "commercial.supermarket", "leisure.playground"):
        labels["budget_friendly"] = 1

    if price and price >= 3:
        labels["upscale"] = 1
    if _has_cat("accommodation.hotel") and rating >= 4.0:
        labels["upscale"] = 1

    if _has_cat("catering.cafe", "catering.fast_food", "catering.ice_cream",
                "commercial.supermarket", "tourism.information"):
        labels["quick_visit"] = 1

    return labels


def auto_label_places(places: list[PlaceRecord]) -> list[dict[str, Any]]:
    # returns [{"place": PlaceRecord, "labels": {tag: 0|1}}]
    return [{"place": p, "labels": rule_based_labels(p)} for p in places]


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------

class PlaceTagClassifier:

    def __init__(
        self,
        n_estimators: int = 200,
        max_depth: int | None = None,
        min_samples_leaf: int = 5,
        random_state: int = 42,
        class_weight: Literal["balanced", "balanced_subsample"] | None = "balanced_subsample",
    ) -> None:
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.multioutput import MultiOutputClassifier

        base = RandomForestClassifier(
            n_estimators=n_estimators,
            max_depth=max_depth,
            min_samples_leaf=min_samples_leaf,
            random_state=random_state,
            class_weight=class_weight,
            n_jobs=-1,
        )
        self.model      = MultiOutputClassifier(base)
        self.extractor  = PlaceFeatureExtractor()
        self._is_fitted = False

    def train(self, places: list[PlaceRecord], label_dicts: list[dict[str, int]]) -> None:
        if len(places) != len(label_dicts):
            raise ValueError("places and label_dicts must have the same length")

        X = self.extractor.extract_batch(places)
        Y = np.array(
            [[ld.get(tag, 0) for tag in PLACE_TAGS] for ld in label_dicts],
            dtype=np.int8,
        )
        logger.info("Training on %d samples …", len(places))
        self.model.fit(X, Y)
        self._is_fitted = True

    def train_from_auto_labels(self, places: list[PlaceRecord]) -> None:
        # use rule-based labels to bootstrap training before real labels are ready
        labelled    = auto_label_places(places)
        label_dicts = [r["labels"] for r in labelled]
        self.train(places, label_dicts)

    def predict(self, places: list[PlaceRecord]) -> list[list[str]]:
        # returns a list of tag lists, one per place
        self._check_fitted()
        Y = self.model.predict(self.extractor.extract_batch(places))
        return [
            [PLACE_TAGS[j] for j in range(len(PLACE_TAGS)) if row[j] == 1]
            for row in Y
        ]

    def predict_proba(self, places: list[PlaceRecord]) -> list[dict[str, float]]:
        # returns per-tag confidence scores, useful for ranking / soft filtering
        self._check_fitted()
        proba_list = self.model.predict_proba(self.extractor.extract_batch(places))
        return [
            {tag: float(proba_list[j][i, 1]) for j, tag in enumerate(PLACE_TAGS)}
            for i in range(len(places))
        ]

    def tag_places(self, places: list[PlaceRecord]) -> list[PlaceRecord]:
        # main entry point for the backend — returns new dicts with "tags" populated
        tag_lists = self.predict(places)
        return [{**p, "tags": tags} for p, tags in zip(places, tag_lists)]

    def evaluate(self, places: list[PlaceRecord], label_dicts: list[dict[str, int]]) -> dict[str, Any]:
        from sklearn.metrics import classification_report, hamming_loss
        self._check_fitted()
        X      = self.extractor.extract_batch(places)
        Y_true = np.array([[ld.get(tag, 0) for tag in PLACE_TAGS] for ld in label_dicts], dtype=np.int8)
        Y_pred = self.model.predict(X)
        return {
            "per_tag":      classification_report(Y_true, Y_pred, target_names=PLACE_TAGS, output_dict=True, zero_division=0),
            "hamming_loss": hamming_loss(Y_true, Y_pred),
        }

    def save(self, path: str | Path) -> None:
        import joblib  # type: ignore[import-untyped]
        self._check_fitted()
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"model": self.model, "tags": PLACE_TAGS}, path)

    @classmethod
    def load(cls, path: str | Path) -> "PlaceTagClassifier":
        import joblib  # type: ignore[import-untyped]
        data       = joblib.load(path)
        obj        = cls.__new__(cls)
        obj.model      = data["model"]
        obj.extractor  = PlaceFeatureExtractor()
        obj._is_fitted = True
        return obj

    def _check_fitted(self) -> None:
        if not self._is_fitted:
            raise RuntimeError("PlaceTagClassifier is not fitted. Call train() first.")
