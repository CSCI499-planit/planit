from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ml.data.preprocess import PlaceRecord, UserPreference, UserVisit
from ml.models.place_classifier import rule_based_labels
from ml.models.recommender import HybridRecommender
from ml.models.user_profiler import UserProfiler

logger = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    profiler_path:      str = "artifacts/user_profiler.joblib"
    user_embedding_dim: int = 48
    rec_top_k:          int = 20


class MLPipeline:

    def __init__(self, config: PipelineConfig | None = None) -> None:
        self.config        = config or PipelineConfig()
        self.user_profiler = UserProfiler(embedding_dim=self.config.user_embedding_dim)
        self._recommender  = HybridRecommender()

    def run_stage1(self, places: list[PlaceRecord]) -> list[PlaceRecord]:
        logger.info("Stage 1: tagging %d places", len(places))
        tagged = []
        for p in places:
            if p.get("tags"):
                tagged.append(p)
            else:
                tags = [tag for tag, val in rule_based_labels(p).items() if val == 1]
                tagged.append({**p, "tags": tags})
        return tagged

    def train_stage2(
        self,
        visits:      list[UserVisit],
        preferences: list[UserPreference],
    ) -> None:
        self.user_profiler.fit(visits, preferences)

    def run_stage2(
        self,
        preference: UserPreference,
        visits:     list[UserVisit] | None = None,
    ) -> np.ndarray:
        logger.info("Stage 2: embedding user %s", preference.get("user_id", "?"))
        return self.user_profiler.embed_user(preference, visits)

    def find_similar_users(
        self,
        embedding: np.ndarray,
        top_k:     int = 10,
    ) -> list[tuple[str, float]]:
        return self.user_profiler.find_similar_users(embedding, top_k=top_k)

    def run_stage3(
        self,
        user_embedding: np.ndarray,
        tagged_places:  list[PlaceRecord],
        trip_context:   dict,
        log_to_db:      bool = True,
    ) -> list[PlaceRecord]:
        logger.info(
            "Stage 3: scoring %d places (top_k=%d)",
            len(tagged_places), self.config.rec_top_k,
        )
        ranked = self._recommender.recommend(
            user_embedding=user_embedding,
            places=tagged_places,
            preference=trip_context,
            top_k=self.config.rec_top_k,
        )

        if log_to_db and ranked:
            self._log_recommendations(ranked, trip_context.get("user_id", "unknown"))

        return ranked

    def _log_recommendations(
        self,
        ranked:  list[PlaceRecord],
        user_id: str,
    ) -> None:
        try:
            import os
            from supabase import create_client
            sb = create_client(os.getenv("SUPABASE_URL", ""), os.getenv("SUPABASE_KEY", ""))
            rows = []
            for position, place in enumerate(ranked):
                rows.append({
                    "user_id":       user_id,
                    "place_id":      place["place_id"],
                    "rank_position": position,
                    "features": {
                        "cf_score":      place.get("_cf_score",      0.0),
                        "tag_score":     place.get("_tag_score",     0.0),
                        "pop_score":     place.get("_pop_score",     0.0),
                        "cuisine_bonus": place.get("_cuisine_bonus", 0.0),
                        "party_match":   place.get("_party_match",   0.0),
                    },
                    "final_score": place.get("score", 0.0),
                })
            sb.table("recommendation_logs").insert(rows).execute()
        except Exception as e:
            logger.warning("Failed to log recommendations: %s", e, exc_info=True)

    def run_stage4(
        self,
        ranked_places: list[PlaceRecord],
        trip_context:  dict,
    ) -> list[dict]:
        from ml.models.route_optimizer import RouteOptimizer
        logger.info("Stage 4: building itinerary for %d places", len(ranked_places))
        return RouteOptimizer().optimize(ranked_places, trip_context)

    def save(self) -> None:
        self.user_profiler.save(self.config.profiler_path)

    @classmethod
    def load(cls, config: PipelineConfig | None = None) -> "MLPipeline":
        obj = cls(config)
        if Path(obj.config.profiler_path).exists():
            obj.user_profiler = UserProfiler.load(obj.config.profiler_path)
        else:
            logger.warning(
                "No saved profiler at %s — call train_stage2() before embedding users.",
                obj.config.profiler_path,
            )
        return obj
