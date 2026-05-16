# Stage 2 — user preference profiling

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
from scipy.sparse import csr_matrix
from sklearn.decomposition import TruncatedSVD
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import normalize

from ml.data.preprocess import UserPreference, UserVisit
from ml.models.place_classifier import PLACE_TAGS

logger = logging.getLogger(__name__)

# field values must match the survey form exactly
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

# SVD is statistically unreliable below this user count
MIN_SVD_USERS: int = 20

# O(1) lookup dicts — replaces list.index() calls in _encode_preferences
_TAG_IDX:    dict[str, int] = {t: i for i, t in enumerate(ALL_TAGS)}
_CUISINE_IDX: dict[str, int] = {c: i for i, c in enumerate(ALL_CUISINES)}
_DIETARY_IDX: dict[str, int] = {d: i for i, d in enumerate(ALL_DIETARY)}
_TRAVEL_IDX:  dict[str, int] = {m: i for i, m in enumerate(ALL_TRAVEL_MODES)}
_PARTY_IDX:   dict[str, int] = {p: i for i, p in enumerate(ALL_PART_TYPES)}
_USE_IDX:     dict[str, int] = {u: i for i, u in enumerate(ALL_USE_CASES)}

# content vector layout: 15 + 9 + 4 + 5 + 4 + 7 + 4 scalars = 48 dims total
_CONTENT_DIM: int = (
    len(ALL_TAGS)           # 15
    + len(ALL_CUISINES)     # 9
    + len(ALL_TRAVEL_MODES) # 4
    + len(ALL_PART_TYPES)   # 5
    + len(ALL_USE_CASES)    # 4
    + len(ALL_DIETARY)      # 7
    + 4                     # scalars: budget tiers, exploration, popularity
)  # = 48

EMBEDDING_DIM: int = 48  # must equal _CONTENT_DIM
assert _CONTENT_DIM == EMBEDDING_DIM, (
    f"Content dim {_CONTENT_DIM} must equal EMBEDDING_DIM {EMBEDDING_DIM}. "
    "Update both together or add a learned projection layer."
)

_TAG_DIM: int = len(ALL_TAGS)
_TAIL_DIM: int = EMBEDDING_DIM - _TAG_DIM

PACE_TO_MAX_PLACES: dict[str, int] = {
    "packed":   6,
    "balanced": 4,
    "relaxed":  3,
}


# canonical event → implicit rating mapping; server.controllers.interactions mirrors this
EVENT_RATINGS: dict[str, float] = {
    "like":              4.5,
    "unlike":            1.0,
    "itinerary_like":    5.0,
    "itinerary_dislike": 1.0,
    "google_import":     3.0,
}


def _metadata_float(meta: dict, key: str, default: float) -> float:
    try:
        return float(meta.get(key, default))
    except (TypeError, ValueError):
        return default


def _metadata_int(meta: dict, key: str, default: int) -> int:
    try:
        return max(int(meta.get(key, default)), 1)
    except (TypeError, ValueError):
        return default


def _metadata_tags(meta: dict) -> list[str]:
    raw = meta.get("tags") or []
    if isinstance(raw, str):
        return [tag.strip() for tag in raw.split(",") if tag.strip()]
    if isinstance(raw, list):
        return [str(tag).strip() for tag in raw if str(tag).strip()]
    return []


def parse_app_interactions(
    interactions: list[dict],
    user_id:      str | None = None,
    place_tag_db: dict[str, list[str]] | None = None,
) -> list[UserVisit]:
    place_tag_db = place_tag_db or {}
    aggregated: dict[tuple[str, str], dict] = {}

    for row in interactions:
        row_user = row.get("user_id", "")
        if user_id is not None and row_user != user_id:
            continue
        place_id   = row["place_id"]
        event_type = row.get("event_type", "view")
        meta       = row.get("metadata") or {}
        if event_type == "google_import":
            rating = _metadata_float(meta, "rating", EVENT_RATINGS["google_import"])
            visit_count = _metadata_int(meta, "visit_count", 1)
        else:
            rating = EVENT_RATINGS.get(event_type, 2.5)
            visit_count = 1

        key = (row_user, place_id)
        if key not in aggregated:
            # prefer place_tag_db; fall back to metadata.tags (set by simulation)
            tags = place_tag_db.get(place_id) or _metadata_tags(meta)
            aggregated[key] = {
                "user_id":     row_user,
                "place_id":    place_id,
                "tags":        tags,
                "ratings":     [],
                "visit_count": 0,
                "created_at":  row.get("created_at"),
            }
        aggregated[key]["ratings"].extend([rating] * visit_count)
        aggregated[key]["visit_count"] += visit_count

    visits: list[UserVisit] = []
    for agg in aggregated.values():
        avg_rating = sum(agg["ratings"]) / len(agg["ratings"])
        visits.append(UserVisit(
            user_id=agg["user_id"],
            place_id=agg["place_id"],
            rating=round(avg_rating, 2),
            visit_count=agg["visit_count"],
            tags=agg["tags"],
            created_at=agg["created_at"],
        ))

    logger.info(
        "Parsed %d interactions → %d unique places (user_id=%s)",
        len(interactions), len(visits), user_id or "all",
    )
    return visits



@dataclass
class UserProfiler:

    embedding_dim: int = EMBEDDING_DIM

    _svd:             TruncatedSVD     | None = field(default=None,  repr=False, init=False)
    _knn:             NearestNeighbors | None = field(default=None,  repr=False, init=False)
    _user_embeddings: np.ndarray       | None = field(default=None,  repr=False, init=False)
    _user_ids:        list[str]               = field(default_factory=list, repr=False, init=False)
    _tag_index:       dict[str, int]          = field(default_factory=dict, repr=False, init=False)
    _n_trained_users: int                     = field(default=0,     repr=False, init=False)
    _cf_w:            float                   = field(default=0.0,   repr=False, init=False)
    _is_fitted:       bool                    = field(default=False, repr=False, init=False)
    # place_id → tags cache: populated by run_stage1 at inference time and
    # persisted inside the joblib artifact so it survives restarts.
    place_tag_db:     dict[str, list[str]]    = field(default_factory=dict, repr=False, init=False)

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
        matrix, interaction_user_ids, tag_index = self._build_interaction_matrix(visits)

        # CF component — only when we have enough interaction data
        n_interaction_users = len(interaction_user_ids)
        cf_w = self._cf_weight(n_interaction_users)
        logger.info("CF weight=%.2f  content weight=%.2f", cf_w, 1.0 - cf_w)

        if n_interaction_users >= MIN_SVD_USERS and matrix.nnz > 0:
            svd_dim   = max(1, min(_TAIL_DIM, matrix.shape[1] - 1, n_interaction_users - 1))
            self._svd = TruncatedSVD(n_components=svd_dim, random_state=42)
            cf_raw    = normalize(_pad(self._svd.fit_transform(matrix), _TAIL_DIM))
            # CF stays out of the tag slots
            cf_lookup = {uid: cf_raw[i] for i, uid in enumerate(interaction_user_ids)}
        else:
            logger.info(
                "Only %d interaction users — skipping SVD (need %d). Content-only mode.",
                n_interaction_users, MIN_SVD_USERS,
            )
            cf_w      = 0.0
            cf_lookup = {}

        # user_ids = union of interaction users + preference-only users
        all_user_ids = list(dict.fromkeys(interaction_user_ids + [
            uid for uid in pref_map if uid not in set(interaction_user_ids)
        ]))

        if not all_user_ids:
            self._is_fitted = False
            logger.warning("No users to fit — pipeline remains in cold-start mode.")
            return self

        self._user_ids        = all_user_ids
        self._tag_index       = tag_index
        self._n_trained_users = n_interaction_users  # CF count, not total
        self._cf_w            = self._cf_weight(n_interaction_users)

        tag_lookup = self._build_user_tag_lookup(visits, tag_index)

        content_raw = [self._encode_preferences(pref_map.get(uid)) for uid in all_user_ids]
        cf_tail = [
            cf_lookup.get(uid, np.zeros(_TAIL_DIM, dtype=np.float32))
            for uid in all_user_ids
        ]

        self._user_embeddings = np.vstack([
            self._compose_embedding(content_raw[i], tag_lookup.get(uid), cf_tail[i], cf_w)
            for i, uid in enumerate(all_user_ids)
        ])

        self._knn = NearestNeighbors(metric="cosine", algorithm="brute")
        self._knn.fit(self._user_embeddings)

        self._is_fitted = True
        logger.info("Fitting complete. Embedding matrix shape: %s", self._user_embeddings.shape)
        return self

    def embed_user(
        self,
        preference: UserPreference,
        visits:     list[UserVisit] | None = None,
    ) -> np.ndarray:
        if not preference or not preference.get("user_id"):
            logger.warning(
                "embed_user called with no preference data — "
                "returning zero vector. Popularity fallback will activate."
            )

        content_raw = self._encode_preferences(preference)
        tag_vec = self._visits_to_tag_vector(visits) if self._tag_index and visits else (
            self._visits_to_fixed_tag_vector(visits) if visits else None
        )

        # no visit history, model not trained, or SVD unavailable
        if not self._is_fitted or not visits or self._svd is None:
            return self._compose_embedding(content_raw, tag_vec)

        cf_raw  = self._svd.transform(tag_vec[np.newaxis])
        cf_emb  = _pad(cf_raw, _TAIL_DIM)[0]
        cf_norm = np.linalg.norm(cf_emb)
        if cf_norm < 1e-9:
            return self._compose_embedding(content_raw, tag_vec)
        cf_emb /= cf_norm

        return self._compose_embedding(content_raw, tag_vec, cf_emb, self._cf_w)

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

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)
        logger.info("UserProfiler saved to %s", path)

    @classmethod
    def load(cls, path: str | Path) -> "UserProfiler":
        profiler = joblib.load(path)
        # backward-compat: artifacts saved before place_tag_db was added won't have the attr
        if not hasattr(profiler, "place_tag_db"):
            profiler.place_tag_db = {}
        logger.info("UserProfiler loaded from %s", path)
        return profiler

    @staticmethod
    # ramping up of CF
    def _cf_weight(n_users: int, target_users: int = 100) -> float:
        # ramps CF contribution 0 → 0.8 as user count grows 0 → 100
        # at 29 users: 0.23  
        # at 50 users: 0.40
        # at 100 users: 0.80  (max CF contribution)
        return 0.8 * min(n_users / target_users, 1.0)

    @staticmethod
    def _recency_weight(created_at: str | None, half_life_days: float = 60.0) -> float:
        if not created_at:
            return 1.0
        try:
            from datetime import timezone as _tz
            ts = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            days = (datetime.now(_tz.utc) - ts).total_seconds() / 86400
            return math.exp(-math.log(2) * max(days, 0) / half_life_days)
        except Exception:
            return 1.0

    def _build_interaction_matrix(
        self,
        visits: list[UserVisit],
    ) -> tuple[csr_matrix, list[str], dict[str, int]]:
        # sparse user × tag matrix; cell = rating × visit_count × recency_weight
        tagged_visits = [v for v in visits if v.get("tags")]
        tag_index  = {tag: i for i, tag in enumerate(ALL_TAGS)}
        user_ids   = list(dict.fromkeys(v["user_id"] for v in tagged_visits))
        user_index = {uid: i for i, uid in enumerate(user_ids)}

        rows, cols, data = [], [], []
        for v in tagged_visits:
            recency = self._recency_weight(v.get("created_at"))
            score   = float(v.get("rating") or 3.0) * max(int(v.get("visit_count") or 1), 1) * recency
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
        # same rating × visit_count weighting as the training matrix
        vec = np.zeros(len(self._tag_index))
        for v in visits:
            score = float(v.get("rating") or 3.0) * max(int(v.get("visit_count") or 1), 1)
            for tag in (v.get("tags") or []):
                if tag in self._tag_index:
                    vec[self._tag_index[tag]] += score
        return vec

    def _build_user_tag_lookup(
        self,
        visits: list[UserVisit],
        tag_index: dict[str, int],
    ) -> dict[str, np.ndarray]:
        lookup: dict[str, np.ndarray] = {}
        for v in visits:
            tags = v.get("tags") or []
            if not tags:
                continue
            uid = v["user_id"]
            vec = lookup.setdefault(uid, np.zeros(len(tag_index), dtype=np.float32))
            score = float(v.get("rating") or 3.0) * max(int(v.get("visit_count") or 1), 1)
            for tag in tags:
                if tag in tag_index:
                    vec[tag_index[tag]] += score
        return lookup

    @staticmethod
    def _compose_embedding(
        content_raw: np.ndarray,
        tag_vec:     np.ndarray | None = None,
        cf_tail:     np.ndarray | None = None,
        cf_w:        float = 0.0,
    ) -> np.ndarray:
        emb = np.zeros(EMBEDDING_DIM, dtype=np.float32)

        survey_tags = content_raw[:_TAG_DIM]
        if tag_vec is not None and np.linalg.norm(tag_vec) > 1e-9:
            direct_tags = normalize(_pad(tag_vec[np.newaxis], _TAG_DIM))[0]
            tag_w = cf_w if cf_w > 0 else 0.5
            tag_part = (1.0 - tag_w) * survey_tags + tag_w * direct_tags
        else:
            tag_part = survey_tags
        tag_norm = np.linalg.norm(tag_part)
        emb[:_TAG_DIM] = tag_part / (tag_norm + 1e-9)

        tail = _pad(content_raw[_TAG_DIM:][np.newaxis], _TAIL_DIM)[0]
        if cf_tail is not None and np.linalg.norm(cf_tail) > 1e-9:
            cf_tail = _pad(cf_tail[np.newaxis], _TAIL_DIM)[0]
            tail = (1.0 - cf_w) * tail + cf_w * cf_tail
        tail_norm = np.linalg.norm(tail)
        emb[_TAG_DIM:] = tail / (tail_norm + 1e-9)

        return emb

    @staticmethod
    def _visits_to_fixed_tag_vector(visits: list[UserVisit]) -> np.ndarray:
        vec = np.zeros(_TAG_DIM, dtype=np.float32)
        for v in visits:
            score = float(v.get("rating") or 3.0) * max(int(v.get("visit_count") or 1), 1)
            for tag in (v.get("tags") or []):
                if tag in _TAG_IDX:
                    vec[_TAG_IDX[tag]] += score
        return vec

    @staticmethod
    def _encode_preferences(pref: UserPreference | None) -> np.ndarray:
        # encodes a user's survey into a 48-dim vector
        # layout:
        #   [0 :15]  preferred_tags one-hot
        #   [15:24]  cuisine_preferences one-hot
        #   [24:28]  travel_mode one-hot
        #   [28:33]  party_type one-hot
        #   [33:37]  use_case one-hot
        #   [37:44]  dietary_restrictions one-hot
        #   [44:48]  scalars (budget tiers, exploration, popularity) normalised to [0,1]
        vec = np.zeros(_CONTENT_DIM, dtype=np.float32)
        if pref is None:
            return vec

        offset = 0

        for tag in (pref.get("preferred_tags") or []):
            if tag in _TAG_IDX:
                vec[offset + _TAG_IDX[tag]] = 1.0
        offset += len(ALL_TAGS)

        for c in (pref.get("cuisine_preferences") or []):
            if c in _CUISINE_IDX:
                vec[offset + _CUISINE_IDX[c]] = 1.0
        offset += len(ALL_CUISINES)

        for m in (pref.get("travel_mode") or []):
            if m in _TRAVEL_IDX:
                vec[offset + _TRAVEL_IDX[m]] = 1.0
        offset += len(ALL_TRAVEL_MODES)

        pt = pref.get("party_type", "")
        if pt in _PARTY_IDX:
            vec[offset + _PARTY_IDX[pt]] = 1.0
        offset += len(ALL_PART_TYPES)

        uc = pref.get("use_case", "")
        if uc in _USE_IDX:
            vec[offset + _USE_IDX[uc]] = 1.0
        offset += len(ALL_USE_CASES)

        for d in (pref.get("dietary_restrictions") or []):
            if d in _DIETARY_IDX:
                vec[offset + _DIETARY_IDX[d]] = 1.0
        offset += len(ALL_DIETARY)

        # normalise scalars to [0, 1] so they're on the same scale as the one-hots
        vec[offset]     = (float(pref.get("daily_budget_tier") or 2) - 1.0) / 3.0
        trip_tier       = pref.get("trip_budget_tier")
        vec[offset + 1] = (float(trip_tier) - 1.0) / 3.0 if trip_tier is not None else 0.0
        vec[offset + 2] = (float(pref.get("exploration_score") or 3) - 1.0) / 4.0
        vec[offset + 3] = (float(pref.get("popularity_weight") or 3) - 1.0) / 4.0

        return vec


def _pad(arr: np.ndarray, dim: int) -> np.ndarray:
    # pads or truncates the last dimension to match the target embedding size
    current = arr.shape[-1]
    if current == dim:
        return arr
    if current < dim:
        return np.pad(arr, [(0, 0)] * (arr.ndim - 1) + [(0, dim - current)])
    return arr[..., :dim]
