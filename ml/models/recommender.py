# Stage 3 — Hybrid Recommendation Engine
#
# Score weights: cf=0.30  tag=0.35  popularity=0.20  cuisine=0.05  party=0.10
# Hard filters (budget, dietary) zero the score before weighting runs.
# Falls back to popularity ranking if all places score 0.

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING

import numpy as np

from ml.models.place_classifier import PLACE_TAGS
from ml.models.user_profiler import EMBEDDING_DIM
from ml.utilities.embeddings import cosine_similarity

if TYPE_CHECKING:
    from ml.data.preprocess import PlaceRecord, UserPreference

logger = logging.getLogger(__name__)

_N_TAGS = len(PLACE_TAGS)  # 15

# Approximate max — needs tuning against real data.
# A 5-star place with ~54k reviews gives 5 × ln(54001) ≈ 54, but using 25.0
# gives a gentler curve so one viral venue doesn't dominate the ranking.
_POPULARITY_NORM = 25.0

# Bayesian prior for popularity scoring.
# When a place has little or no review data we shrink its score toward the prior
# instead of zeroing it out — avoids unfairly burying new or unreviewed places.
_PRIOR_RATING = 3.5
_PRIOR_COUNT  = 10

# dietary restrictions that map to a place tag we can filter on
# restrictions not in this map (gluten_free, nut_allergy, dairy_free) can't be
# filtered reliably from category/tag data alone — need enriched place data for those
_DIETARY_TAG_FILTER: dict[str, str] = {
    "vegetarian": "vegetarian",
    "vegan":      "vegetarian",   # vegetarian tag is the closest we have for vegan
    "halal":      "halal",
}


def _place_embedding(place: PlaceRecord) -> np.ndarray:
    # binary tag vector, zero-padded to the full embedding dim so cosine sim works
    place_tags = set(place.get("tags") or [])
    vec = np.zeros(EMBEDDING_DIM, dtype=np.float32)
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


class HybridRecommender:

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
        if price is not None and price > preference.get("daily_budget_tier", 4):
            return _zero

        dietary = set(preference.get("dietary_restrictions") or [])
        if dietary and "food_and_drink" in place_tags:
            for restriction, required_tag in _DIETARY_TAG_FILTER.items():
                if restriction in dietary and required_tag not in place_tags:
                    return _zero

        place_emb = _place_embedding(place)

        cf_score = max(0.0, cosine_similarity(user_embedding, place_emb))

        preferred = preference.get("preferred_tags") or []
        tag_score = len(set(preferred) & place_tags) / max(len(preferred), 1)

        rating       = place.get("rating")
        review_count = place.get("review_count")
        pop_weight   = preference.get("popularity_weight", 3) / 5.0

        if rating is not None and review_count is not None:
            rc       = float(review_count)
            bayesian = (_PRIOR_COUNT * _PRIOR_RATING + rc * float(rating)) / (_PRIOR_COUNT + rc)
            raw_pop  = bayesian * math.log1p(rc)
        else:
            raw_pop = _PRIOR_RATING * math.log1p(1)

        popularity_score = min(raw_pop / _POPULARITY_NORM, 1.0) * pop_weight

        cuisine_bonus = 0.0
        if "food_and_drink" in place_tags:
            cuisines       = preference.get("cuisine_preferences") or []
            place_cuisines = _get_cuisine_from_attributes(place.get("attributes"))
            if cuisines and place_cuisines:
                if any(c.lower() in place_cuisines for c in cuisines):
                    cuisine_bonus = 1.0

        party_type = preference.get("party_type", "")
        if party_type == "family" and "family_friendly" in place_tags:
            party_match = 1.0
        elif party_type == "couple" and "romantic" in place_tags:
            party_match = 1.0
        else:
            party_match = 0.0

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

    def score_place(
        self,
        user_embedding: np.ndarray,
        place: PlaceRecord,
        preference: UserPreference,
    ) -> float:
        return self._score_place_with_breakdown(user_embedding, place, preference)["score"]

    def recommend(
        self,
        user_embedding: np.ndarray,
        places: list[PlaceRecord],
        preference: UserPreference,
        top_k: int = 20,
    ) -> list[PlaceRecord]:
        scored: list[tuple[float, PlaceRecord, dict]] = []
        for place in places:
            bd = self._score_place_with_breakdown(user_embedding, place, preference)
            if bd["score"] > 0.0:
                scored.append((bd["score"], place, bd))

        scored.sort(key=lambda x: x[0], reverse=True)

        if not scored:
            logger.info("All places filtered or zero-scored — using popularity fallback.")
            return self.popularity_fallback(places, top_k)

        exploration = int(preference.get("exploration_score") or 3)
        ranked = self._rerank_for_diversity(scored, exploration, top_k)

        return [{
            **place,
            "score":          round(score, 4),
            "_cf_score":      round(bd["cf_score"], 4),
            "_tag_score":     round(bd["tag_score"], 4),
            "_pop_score":     round(bd["pop_score"], 4),
            "_cuisine_bonus": round(bd["cuisine_bonus"], 4),
            "_party_match":   round(bd["party_match"], 4),
        } for score, place, bd in ranked]

    @staticmethod
    def popularity_fallback(
        places: list[PlaceRecord],
        top_k:  int = 20,
    ) -> list[PlaceRecord]:
        """Last-resort fallback when all scored places return 0."""
        def _pop_score(place: PlaceRecord) -> float:
            rating = place.get("rating")
            rc     = place.get("review_count")
            if rating is None or rc is None:
                return _PRIOR_RATING * math.log1p(1)
            bayesian = (_PRIOR_COUNT * _PRIOR_RATING + float(rc) * float(rating)) / (_PRIOR_COUNT + float(rc))
            return bayesian * math.log1p(float(rc))

        ranked = sorted(places, key=_pop_score, reverse=True)
        return [
            {**p, "score": round(min(_pop_score(p) / _POPULARITY_NORM, 1.0), 4), "_fallback": True}
            for p in ranked[:top_k]
        ]

    @staticmethod
    def _jaccard(a: set[str], b: set[str]) -> float:
        # |A ∩ B| / |A ∪ B| on tag sets
        # returns 0.0 for empty inputs so the first pick is never penalised
        if not a or not b:
            return 0.0
        return len(a & b) / len(a | b)

    def _rerank_for_diversity(
        self,
        scored: list[tuple[float, PlaceRecord, dict]],
        exploration_score: int,
        top_k: int,
    ) -> list[tuple[float, PlaceRecord, dict]]:
        # MMR re-ranking: lambda maps exploration_score 1–5 → 0.00–0.28
        # score 1 → pure relevance, score 5 → strong diversity push
        if not scored:
            return scored[:top_k]

        diversity_lambda = 0.07 * (exploration_score - 1)

        candidates    = list(scored)
        selected      = []
        selected_tags = set()

        while candidates and len(selected) < top_k:
            best_idx = 0
            best_adj = -float("inf")

            for i, (score, place, bd) in enumerate(candidates):
                place_tags = set(place.get("tags") or [])
                penalty    = diversity_lambda * self._jaccard(place_tags, selected_tags)
                adj_score  = score - penalty
                if adj_score > best_adj:
                    best_adj = adj_score
                    best_idx = i

            score, place, bd = candidates.pop(best_idx)
            selected.append((score, place, bd))
            selected_tags |= set(place.get("tags") or [])

        return selected
