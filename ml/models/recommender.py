# Stage 3 — Hybrid Recommendation Engine
# Score weights: cf=0.30  tag=0.35  popularity=0.20  cuisine=0.05  party=0.10

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING

import numpy as np

from ml.models.place_classifier import PLACE_TAGS
from ml.utilities.embeddings import cosine_similarity

if TYPE_CHECKING:
    from ml.data.preprocess import PlaceRecord, UserPreference

logger = logging.getLogger(__name__)

_N_TAGS = len(PLACE_TAGS)  # 15

_POPULARITY_NORM = 25.0  # gentler curve so one viral venue doesn't dominate

# Bayesian prior shrinks unreviewed places toward 3.5 rather than zeroing them
_PRIOR_RATING = 3.5
_PRIOR_COUNT = 10

# only hard-filter diets Geoapify can actually confirm
_HARD_DIETARY = {"vegetarian", "vegan"}

# party-type → relevant tags; score is proportional (matching tags / total affinity tags)
# solo/friends/mixed were previously hardcoded to 0 — this restores the full 10% weight
_PARTY_TAG_AFFINITIES: dict[str, list[str]] = {
    "solo":    ["quick_visit", "cultural", "historical", "scenic"],
    "couple":  ["romantic", "upscale", "scenic", "food_and_drink"],
    "friends": ["nightlife", "adventurous", "food_and_drink", "outdoor"],
    "family":  ["family_friendly", "outdoor", "budget_friendly", "food_and_drink"],
    "mixed":   ["outdoor", "food_and_drink", "cultural"],
}


def _place_embedding(place: PlaceRecord) -> np.ndarray:
    # _N_TAGS-dim only — caller must slice user_embedding[:_N_TAGS] to align
    place_tags = set(place.get("tags") or [])
    vec = np.zeros(_N_TAGS, dtype=np.float32)
    for i, tag in enumerate(PLACE_TAGS):
        if tag in place_tags:
            vec[i] = 1.0
    return vec


def _get_cuisine_from_attributes(attrs: dict | None) -> list[str]:
    if not attrs:
        return []
    raw = attrs.get("cuisine")
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(c).lower().strip() for c in raw]
    return [c.lower().strip() for c in str(raw).split(",") if c.strip()]


def _get_diet_from_attributes(attrs: dict | None) -> set[str]:
    if not attrs:
        return set()
    raw = attrs.get("diet")
    if raw is None:
        return set()
    if isinstance(raw, dict):
        return {
            str(k).lower().strip()
            for k, v in raw.items()
            if str(v).lower() in ("true", "1", "yes")
        }
    if isinstance(raw, list):
        return {str(d).lower().strip() for d in raw}
    return {d.lower().strip() for d in str(raw).split(",") if d.strip()}


def _passes_dietary_filter(place: PlaceRecord, dietary: set[str]) -> bool:
    required = dietary & _HARD_DIETARY
    if not required:
        return True
    diets = _get_diet_from_attributes(place.get("attributes"))
    if not diets:
        return True
    if "vegan" in required:
        return "vegan" in diets
    return bool({"vegetarian", "vegan"} & diets)


class HybridRecommender:

    def __init__(self) -> None:
        # populated by _fetch_and_train; used as pop_score proxy when
        # Geoapify returns null rating/review_count
        self.interaction_counts: dict[str, int] = {}

    def _score_place_with_breakdown(
        self,
        user_embedding: np.ndarray,
        place: PlaceRecord,
        preference: UserPreference,
    ) -> dict:
        _zero = {
            "score": 0.0, "cf_score": 0.0, "tag_score": 0.0,
            "pop_score": 0.0, "cuisine_bonus": 0.0, "party_match": 0.0,
        }
        place_tags = set(place.get("tags") or [])

        price = place.get("price_level")
        budget_tier = preference.get("daily_budget_tier") or 4
        if price is not None and price > budget_tier:
            return _zero

        dietary = set(preference.get("dietary_restrictions") or [])
        if dietary and "food_and_drink" in place_tags:
            if not _passes_dietary_filter(place, dietary):
                return _zero

        place_emb = _place_embedding(place)

        # slice user embedding to tag subspace so both vectors are _N_TAGS-dim
        cf_score = max(0.0, cosine_similarity(
            user_embedding[:_N_TAGS], place_emb))

        preferred = preference.get("preferred_tags") or []
        tag_score = len(set(preferred) & place_tags) / max(len(preferred), 1)

        rating = place.get("rating")
        review_count = place.get("review_count")
        pop_weight = (preference.get("popularity_weight") or 3) / 5.0

        if rating is not None and review_count is not None:
            rc = float(review_count)
            bayesian = (_PRIOR_COUNT * _PRIOR_RATING + rc *
                        float(rating)) / (_PRIOR_COUNT + rc)
            raw_pop = bayesian * math.log1p(rc)
            popularity_score = min(
                raw_pop / _POPULARITY_NORM, 1.0) * pop_weight
        else:
            # Geoapify free tier never returns rating/review_count.
            # Use accumulated interaction count as an engagement proxy:
            # places that more users have liked/visited score higher.
            proxy_count = self.interaction_counts.get(
                place.get("place_id") or "", 0)
            if proxy_count > 0:
                raw_pop = _PRIOR_RATING * math.log1p(proxy_count)
                popularity_score = min(
                    raw_pop / _POPULARITY_NORM, 1.0) * pop_weight
            else:
                popularity_score = 0.0

        cuisine_bonus = 0.0
        if "food_and_drink" in place_tags:
            cuisines = preference.get("cuisine_preferences") or []
            place_cuisines = _get_cuisine_from_attributes(
                place.get("attributes"))
            if cuisines and place_cuisines:
                if any(c.lower() in place_cuisines for c in cuisines):
                    cuisine_bonus = 1.0

        party_type = preference.get("party_type", "")
        affinity_tags = set(_PARTY_TAG_AFFINITIES.get(party_type, []))
        party_match = (len(affinity_tags & place_tags) / len(affinity_tags)
                       if affinity_tags else 0.0)

        score = min(
            0.30 * cf_score
            + 0.35 * tag_score
            + 0.20 * popularity_score
            + 0.05 * cuisine_bonus
            + 0.10 * party_match,
            1.0,
        )

        return {
            "score":         score,
            "cf_score":      cf_score,
            "tag_score":     tag_score,
            "pop_score":     popularity_score,
            "cuisine_bonus": cuisine_bonus,
            "party_match":   party_match,
        }

    def recommend(
        self,
        user_embedding:    np.ndarray,
        places:            list[PlaceRecord],
        preference:        UserPreference,
        top_k:             int = 20,
        excluded_ids:      set[str] | None = None,
    ) -> list[PlaceRecord]:
        excluded_ids = excluded_ids or set()
        scored: list[tuple[float, PlaceRecord, dict]] = []
        for place in places:
            if place.get("place_id") in excluded_ids:
                continue
            bd = self._score_place_with_breakdown(
                user_embedding, place, preference)
            if bd["score"] > 0.0:
                scored.append((bd["score"], place, bd))

        scored.sort(key=lambda x: x[0], reverse=True)

        if not scored:
            logger.info(
                "All places filtered or zero-scored — using popularity fallback.")
            return self.popularity_fallback(places, top_k)

        exploration = int(preference.get("exploration_score") or 3)
        ranked = self._rerank_for_diversity(scored, exploration, top_k)

        return [{
            **place,
            "score": round(score, 4),
            "score_breakdown": {
                "cf_score":      round(bd["cf_score"], 4),
                "tag_score":     round(bd["tag_score"], 4),
                "pop_score":     round(bd["pop_score"], 4),
                "cuisine_bonus": round(bd["cuisine_bonus"], 4),
                "party_match":   round(bd["party_match"], 4),
            },
            "fallback": False,
        } for score, place, bd in ranked]

    @staticmethod
    def popularity_fallback(
        places: list[PlaceRecord],
        top_k:  int = 20,
    ) -> list[PlaceRecord]:
        def _pop_score(place: PlaceRecord) -> float:
            rating = place.get("rating")
            rc = place.get("review_count")
            if rating is None or rc is None:
                return _PRIOR_RATING * math.log1p(1)
            bayesian = (_PRIOR_COUNT * _PRIOR_RATING + float(rc)
                        * float(rating)) / (_PRIOR_COUNT + float(rc))
            return bayesian * math.log1p(float(rc))

        ranked = sorted(places, key=_pop_score, reverse=True)
        return [
            {**p, "score": round(min(_pop_score(p) /
                                 _POPULARITY_NORM, 1.0), 4), "fallback": True}
            for p in ranked[:top_k]
        ]

    @staticmethod
    def _jaccard(a: set[str], b: set[str]) -> float:
        if not a or not b:
            return 0.0
        return len(a & b) / len(a | b)

    def _rerank_for_diversity(
        self,
        scored: list[tuple[float, PlaceRecord, dict]],
        exploration_score: int,
        top_k: int,
    ) -> list[tuple[float, PlaceRecord, dict]]:
        # MMR re-ranking: exploration_score 1–5 maps to diversity lambda 0.00–0.28
        if not scored:
            return scored[:top_k]

        diversity_lambda = 0.07 * (exploration_score - 1)

        candidates = list(scored)
        selected = []
        selected_tags = set()

        while candidates and len(selected) < top_k:
            best_idx = 0
            best_adj = -float("inf")

            for i, (score, place, bd) in enumerate(candidates):
                place_tags = set(place.get("tags") or [])
                penalty = diversity_lambda * self._jaccard(
                    place_tags, selected_tags)
                adj_score = score - penalty
                if adj_score > best_adj:
                    best_adj = adj_score
                    best_idx = i

            score, place, bd = candidates.pop(best_idx)
            selected.append((score, place, bd))
            selected_tags |= set(place.get("tags") or [])

        return selected
