# Stage 2 — user preference profiling
# Blends survey content-encoding with collaborative filtering (TruncatedSVD) into a 64-dim embedding.
# CF weight ramps up as the user base grows; starts content-only to handle cold start.

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from scipy.sparse import csr_matrix
from sklearn.decomposition import TruncatedSVD
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import normalize

from ml.data.preprocess import UserPreference, UserVisit
from ml.models.place_classifier import PLACE_TAGS

logger = logging.getLogger(__name__)

# these must match the preference form exactly

ALL_TAGS: list[str] = PLACE_TAGS   # 15 place tags from Stage 1

ALL_CUISINES: list[str] = [
    "american", "italian", "east asian", "southeast asian",
    "mexican", "indian", "mediterranean", "vegetarian", "seafood",
]

ALL_DIETARY: list[str] = [
    "vegetarian", "vegan", "gluten_free", "halal",
    "kosher", "nut_allergy", "dairy_free",
]

ALL_TRAVEL_MODES: list[str] = ["walk", "bike", "transit", "drive"]

ALL_PART_TYPES: list[str] = ["solo", "couple", "friends", "family", "mixed"]

ALL_USE_CASES: list[str] = ["local", "daytrip", "travel", "mixed"]

MIN_CF_USERS: int = 50  # below this threshold, stay content-based only

# Content vector is 48 dims total (see _encode_preferences), padded to EMBEDDING_DIM
_CONTENT_DIM: int = (
    len(ALL_TAGS)           # 15
    + len(ALL_CUISINES)     # 9
    + len(ALL_TRAVEL_MODES) # 4
    + len(ALL_PART_TYPES)   # 5
    + len(ALL_USE_CASES)    # 4
    + len(ALL_DIETARY)      # 7
    + 4                     # scalar: budget tiers, exploration, popularity
)  # = 48

EMBEDDING_DIM: int = 64  # matches PipelineConfig.user_embedding_dim

# Google Maps dwell time -> implicit rating mapping
# Short stays are likely pass-bys; long stays signal real interest
_DURATION_RATING_BREAKPOINTS: list[tuple[int, float]] = [
    (5,  1.5),   # < 5 min  — probably just drove past
    (15, 2.5),   # 5-15     — quick stop
    (45, 3.5),   # 15-45    — normal visit
    (90, 4.0),   # 45-90    — extended visit
]
_DURATION_MAX_RATING: float = 4.5  # 90+ min


# ---------------------------------------------------------------------------
# Itinerary pace helper  (Stage 4 reads this)
# ---------------------------------------------------------------------------

PACE_TO_MAX_PLACES: dict[str, int] = {
    "packed":   6,
    "balanced": 4,
    "relaxed":  2,
}


def pace_to_max_places(pace: str) -> int:
    return PACE_TO_MAX_PLACES.get(pace.lower(), 4)


# Google Takeout parsers

def parse_google_takeout(
    takeout_data:   dict[str, Any] | list[dict[str, Any]],
    user_id:        str,
    place_tag_db:   dict[str, list[str]],
    min_confidence: float = 50.0,
) -> list[UserVisit]:
    """Parse Semantic Location History JSON into UserVisit records.
    Accepts a single month dict or a list of months merged by the caller.
    Dwell time is used as an implicit rating since there are no explicit ratings.
    """
    months = [takeout_data] if isinstance(takeout_data, dict) else takeout_data

    # Aggregate visits per place before building UserVisit records
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

            # use placeId as key when available, fall back to name
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


# Google Maps Reviews / Saved Places parsers

# Keyword → tags inference for place names.
# Used when we can't match a Google Maps place to our business database.
_NAME_KEYWORDS_TO_TAGS: dict[str, list[str]] = {
    # food & drink
    "restaurant":   ["food_and_drink"],
    "kitchen":      ["food_and_drink"],
    "grill":        ["food_and_drink"],
    "eatery":       ["food_and_drink"],
    "bistro":       ["food_and_drink"],
    "diner":        ["food_and_drink"],
    "buffet":       ["food_and_drink"],
    "sushi":        ["food_and_drink"],
    "pizza":        ["food_and_drink"],
    "burger":       ["food_and_drink", "quick_visit"],
    "empanada":     ["food_and_drink"],
    "shawarma":     ["food_and_drink"],
    "gyro":         ["food_and_drink"],
    "halal":        ["food_and_drink"],
    "baguette":     ["food_and_drink", "quick_visit"],
    "bakery":       ["food_and_drink", "quick_visit"],
    "bites":        ["food_and_drink"],
    "cafe":         ["food_and_drink", "quick_visit"],
    "café":         ["food_and_drink", "quick_visit"],
    "coffee":       ["food_and_drink", "quick_visit"],
    "starbucks":    ["food_and_drink", "quick_visit"],
    "mcdonald":     ["food_and_drink", "quick_visit", "budget_friendly"],
    "chick-fil-a":  ["food_and_drink", "quick_visit", "budget_friendly"],
    "subway":       ["food_and_drink", "quick_visit", "budget_friendly"],
    "burger king":  ["food_and_drink", "quick_visit", "budget_friendly"],
    "panda express": ["food_and_drink", "quick_visit"],
    "olive garden": ["food_and_drink"],
    # nightlife
    "bar":          ["nightlife", "food_and_drink"],
    "lounge":       ["nightlife"],
    "hookah":       ["nightlife"],
    "club":         ["nightlife"],
    "brewery":      ["nightlife", "food_and_drink"],
    # outdoor
    "park":         ["outdoor", "scenic", "pet_friendly"],
    "playground":   ["outdoor", "family_friendly"],
    "beach":        ["outdoor", "scenic", "adventurous"],
    "garden":       ["outdoor", "scenic", "romantic"],
    "pier":         ["outdoor", "scenic"],
    "trail":        ["outdoor", "adventurous"],
    # shopping
    "mall":         ["shopping"],
    "plaza":        ["shopping"],
    "market":       ["shopping", "food_and_drink"],
    "ikea":         ["shopping"],
    # wellness / fitness
    "gym":          ["wellness"],
    "fitness":      ["wellness"],
    "yoga":         ["wellness"],
    "spa":          ["wellness", "upscale"],
    "physical therapy": ["wellness"],
    "sports club":  ["wellness"],
    "climbing":     ["wellness", "adventurous", "outdoor"],
    "movement":     ["wellness", "adventurous"],   # e.g. "Movement Gowanus"
    # cultural
    "museum":       ["cultural", "historical"],
    "gallery":      ["cultural"],
    "theatre":      ["cultural"],
    "theater":      ["cultural"],
    "cinema":       ["cultural", "quick_visit"],
    "regal":        ["cultural", "quick_visit"],
    # adventurous / family
    "adventure park": ["adventurous", "family_friendly"],
    "amusement":    ["adventurous", "family_friendly"],
    "thrillz":      ["adventurous", "family_friendly"],
    "fair":         ["family_friendly", "shopping"],
}


def _infer_tags_from_name(name: str) -> list[str]:
    """Guess place tags from a place name using keyword matching."""
    name_lower = name.lower()
    tags: set[str] = set()
    for keyword, mapped in _NAME_KEYWORDS_TO_TAGS.items():
        if keyword in name_lower:
            tags.update(mapped)
    return list(tags)


def parse_google_reviews(
    reviews_data: dict[str, Any],
    user_id:      str,
) -> list[UserVisit]:
    """Parse Reviews.json from Google Takeout (Takeout/Maps/Reviews.json).
    GeoJSON FeatureCollection — uses five_star_rating_published as rating.
    Tags are inferred from place name since there's no category field.
    """
    visits: list[UserVisit] = []
    seen: set[str] = set()

    for feature in reviews_data.get("features", []):
        props  = feature.get("properties", {})
        coords = feature.get("geometry", {}).get("coordinates", [0, 0])

        # Skip entries with no location data
        if coords == [0, 0] or "location" not in props:
            continue

        loc    = props["location"]
        name   = loc.get("name", "").strip()
        rating = props.get("five_star_rating_published")

        if not name or rating is None:
            continue

        # Deduplicate by name (a user may have reviewed the same place twice)
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)

        place_id = f"gmap_{name.lower().replace(' ', '_').replace('/', '_')}"
        tags     = _infer_tags_from_name(name)

        visits.append(UserVisit(
            user_id=user_id,
            place_id=place_id,
            rating=float(rating),
            visit_count=1,
            tags=tags,
        ))

    logger.info(
        "Parsed %d places from Google Maps Reviews.json for user %s",
        len(visits), user_id,
    )
    return visits


def parse_google_saved_places(
    saved_data: dict[str, Any],
    user_id:    str,
) -> list[UserVisit]:
    """Parse Saved Places.json from Google Takeout (Takeout/Maps/Saved Places.json).
    No explicit rating — saved places get an implicit score of 3.5.
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
        tags     = _infer_tags_from_name(name)

        visits.append(UserVisit(
            user_id=user_id,
            place_id=place_id,
            rating=3.5,   # implicit: saved = interested but not explicitly rated
            visit_count=1,
            tags=tags,
        ))

    logger.info(
        "Parsed %d places from Google Maps Saved Places.json for user %s",
        len(visits), user_id,
    )
    return visits



@dataclass
class UserProfiler:

    embedding_dim: int = EMBEDDING_DIM
    min_cf_users:  int = MIN_CF_USERS

    _svd:             TruncatedSVD    | None = field(default=None,  repr=False, init=False)
    _knn:             NearestNeighbors | None = field(default=None, repr=False, init=False)
    _user_embeddings: np.ndarray      | None = field(default=None,  repr=False, init=False)
    _user_ids:        list[str]              = field(default_factory=list, repr=False, init=False)
    _tag_index:       dict[str, int]         = field(default_factory=dict, repr=False, init=False)
    _n_trained_users: int                    = field(default=0,     repr=False, init=False)
    _is_fitted:       bool                   = field(default=False, repr=False, init=False)

    # --- Training ---

    def fit(
        self,
        visits:      list[UserVisit],
        preferences: list[UserPreference],
    ) -> "UserProfiler":
        logger.info(
            "Fitting UserProfiler: %d visits, %d preference records",
            len(visits), len(preferences),
        )

        pref_map = {p["user_id"]: p for p in preferences}
        matrix, user_ids, tag_index = self._build_interaction_matrix(visits)
        self._user_ids        = user_ids
        self._tag_index       = tag_index
        self._n_trained_users = len(user_ids)

        cf_w = self._cf_weight(len(user_ids))
        logger.info("CF weight=%.2f  content weight=%.2f", cf_w, 1.0 - cf_w)

        # Collaborative filtering — TruncatedSVD on user x tag matrix
        svd_dim   = max(1, min(self.embedding_dim // 2, matrix.shape[1] - 1, len(user_ids) - 1))
        self._svd = TruncatedSVD(n_components=svd_dim, random_state=42)
        cf_emb    = normalize(_pad(self._svd.fit_transform(matrix), self.embedding_dim))

        # Content-based — encode each user's survey
        content_raw = np.array([self._encode_preferences(pref_map.get(uid)) for uid in user_ids])
        content_emb = normalize(_pad(content_raw, self.embedding_dim))

        self._user_embeddings = normalize(cf_w * cf_emb + (1.0 - cf_w) * content_emb)

        self._knn = NearestNeighbors(metric="cosine", algorithm="brute")
        self._knn.fit(self._user_embeddings)

        self._is_fitted = True
        logger.info("Fitting complete. Embedding matrix shape: %s", self._user_embeddings.shape)
        return self

    # --- Inference ---

    def embed_user(
        self,
        preference: UserPreference,
        visits:     list[UserVisit] | None = None,
    ) -> np.ndarray:
        content_raw = self._encode_preferences(preference)
        content_emb = _pad(content_raw[np.newaxis], self.embedding_dim)[0]
        content_norm = np.linalg.norm(content_emb)
        content_emb  = content_emb / (content_norm + 1e-9)

        # No visit history or model not fitted — return content-only embedding
        if not self._is_fitted or not visits:
            return content_emb

        tag_vec = self._visits_to_tag_vector(visits)
        cf_raw  = self._svd.transform(tag_vec[np.newaxis])
        cf_emb  = _pad(cf_raw, self.embedding_dim)[0]
        cf_norm = np.linalg.norm(cf_emb)
        if cf_norm < 1e-9:
            return content_emb
        cf_emb /= cf_norm

        cf_w     = self._cf_weight(self._n_trained_users)
        combined = cf_w * cf_emb + (1.0 - cf_w) * content_emb
        combined /= np.linalg.norm(combined) + 1e-9
        return combined

    def find_similar_users(
        self,
        embedding: np.ndarray,
        top_k:     int = 10,
    ) -> list[tuple[str, float]]:
        if not self._is_fitted:
            raise RuntimeError("Call fit() before find_similar_users().")

        k = min(top_k + 1, len(self._user_ids))
        distances, indices = self._knn.kneighbors(embedding[np.newaxis], n_neighbors=k)
        return [
            (self._user_ids[idx], float(1.0 - dist))
            for dist, idx in zip(distances[0], indices[0])
        ][:top_k]

    # --- Persistence ---

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)
        logger.info("UserProfiler saved to %s", path)

    @classmethod
    def load(cls, path: str | Path) -> "UserProfiler":
        profiler = joblib.load(path)
        logger.info("UserProfiler loaded from %s", path)
        return profiler

    # --- Internal helpers ---

    @staticmethod
    def _cf_weight(n_users: int, min_users: int = MIN_CF_USERS) -> float:
        # Ramp from 0 to 0.8 as user count grows from MIN_CF_USERS to 5x that
        if n_users < min_users:
            return 0.0
        return 0.8 * min((n_users - min_users) / (4 * min_users), 1.0)

    def _build_interaction_matrix(
        self,
        visits: list[UserVisit],
    ) -> tuple[csr_matrix, list[str], dict[str, int]]:
        # sparse user x tag matrix; cell value = rating * visit_count (unrated defaults to 3.0)
        all_tags_seen: set[str] = set(ALL_TAGS)
        for v in visits:
            all_tags_seen.update(v.get("tags") or [])
        tag_index  = {tag: i for i, tag in enumerate(sorted(all_tags_seen))}
        user_ids   = list(dict.fromkeys(v["user_id"] for v in visits))
        user_index = {uid: i for i, uid in enumerate(user_ids)}

        rows, cols, data = [], [], []
        for v in visits:
            score = float(v.get("rating") or 3.0) * max(int(v.get("visit_count") or 1), 1)
            for tag in (v.get("tags") or []):
                if tag in tag_index:
                    rows.append(user_index[v["user_id"]])
                    cols.append(tag_index[tag])
                    data.append(score)

        return (
            csr_matrix((data, (rows, cols)), shape=(len(user_ids), len(tag_index))),
            user_ids,
            tag_index,
        )

    def _visits_to_tag_vector(self, visits: list[UserVisit]) -> np.ndarray:
        vec = np.zeros(len(self._tag_index))
        for v in visits:
            score = float(v.get("rating") or 3.0) * max(int(v.get("visit_count") or 1), 1)
            for tag in (v.get("tags") or []):
                if tag in self._tag_index:
                    vec[self._tag_index[tag]] += score
        return vec

    @staticmethod
    def _encode_preferences(pref: UserPreference | None) -> np.ndarray:
        # Encodes the preference survey into a 48-dim vector
        # Layout:
        #   [0 :15]  preferred_tags one-hot
        #   [15:24]  cuisine_preferences one-hot
        #   [24:28]  travel_mode one-hot
        #   [28:33]  part_type one-hot
        #   [33:37]  use_case one-hot
        #   [37:44]  dietary_restrictions one-hot
        #   [44:48]  scalar features (budget tiers, exploration, popularity)
        vec = np.zeros(_CONTENT_DIM, dtype=np.float32)
        if pref is None:
            return vec

        offset = 0

        for tag in (pref.get("preferred_tags") or []):
            if tag in ALL_TAGS:
                vec[offset + ALL_TAGS.index(tag)] = 1.0
        offset += len(ALL_TAGS)

        for c in (pref.get("cuisine_preferences") or []):
            if c in ALL_CUISINES:
                vec[offset + ALL_CUISINES.index(c)] = 1.0
        offset += len(ALL_CUISINES)

        for m in (pref.get("travel_mode") or []):
            if m in ALL_TRAVEL_MODES:
                vec[offset + ALL_TRAVEL_MODES.index(m)] = 1.0
        offset += len(ALL_TRAVEL_MODES)

        pt = pref.get("part_type", "")
        if pt in ALL_PART_TYPES:
            vec[offset + ALL_PART_TYPES.index(pt)] = 1.0
        offset += len(ALL_PART_TYPES)

        uc = pref.get("use_case", "")
        if uc in ALL_USE_CASES:
            vec[offset + ALL_USE_CASES.index(uc)] = 1.0
        offset += len(ALL_USE_CASES)

        for d in (pref.get("dietary_restrictions") or []):
            if d in ALL_DIETARY:
                vec[offset + ALL_DIETARY.index(d)] = 1.0
        offset += len(ALL_DIETARY)

        # Normalise scalars to [0, 1]
        vec[offset]     = (float(pref.get("daily_budget_tier") or 2) - 1.0) / 3.0
        trip_tier       = pref.get("trip_budget_tier")
        vec[offset + 1] = (float(trip_tier) - 1.0) / 3.0 if trip_tier is not None else 0.0
        vec[offset + 2] = (float(pref.get("exploration_score") or 3) - 1.0) / 4.0
        vec[offset + 3] = (float(pref.get("popularity_weight") or 3) - 1.0) / 4.0

        return vec



def _pad(arr: np.ndarray, dim: int) -> np.ndarray:
    current = arr.shape[-1]
    if current == dim:
        return arr
    if current < dim:
        return np.pad(arr, [(0, 0)] * (arr.ndim - 1) + [(0, dim - current)])
    return arr[..., :dim]
