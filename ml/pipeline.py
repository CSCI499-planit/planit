# ML pipeline — single entry point for the backend.
# Stage 1: rule-based place tagging (OSM/Geoapify categories)
# Stage 2: user embeddings via CF + content-based survey encoding  (active)
# Stage 3: hybrid recommendation engine — TF Recommenders  (TODO)
# Stage 4: itinerary optimization — OR-Tools VRP  (TODO)

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from ml.data.preprocess import PlaceRecord, UserPreference, UserVisit
from ml.models.place_classifier import rule_based_labels
from ml.models.user_profiler import UserProfiler, parse_google_takeout

logger = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    # Stage 2
    profiler_path:      str       = "artifacts/user_profiler.joblib"
    user_embedding_dim: int       = 64

    # Stage 3 (TODO)
    rec_top_k:          int       = 20

    # Stage 4 (TODO)
    travel_mode:        str       = "drive"  # "drive" | "walk" | "transit" | "bike"


class MLPipeline:

    def __init__(self, config: PipelineConfig | None = None) -> None:
        self.config        = config or PipelineConfig()
        self.user_profiler = UserProfiler(embedding_dim=self.config.user_embedding_dim)

        # Stages 3 & 4 — not yet implemented
        self._recommender:     Any = None
        self._route_optimizer: Any = None

    # -----------------------------------------------------------------------
    # Stage 1: Place Tagging  (rule-based, stateless)
    # -----------------------------------------------------------------------

    def run_stage1(self, places: list[PlaceRecord]) -> list[PlaceRecord]:
        logger.info("Stage 1: tagging %d places (rule-based)", len(places))
        tagged = []
        for p in places:
            if p.get("tags"):
                tagged.append(p)
            else:
                tags = [tag for tag, val in rule_based_labels(p).items() if val == 1]
                tagged.append({**p, "tags": tags})
        return tagged

    # -----------------------------------------------------------------------
    # Stage 2: User Preference Profiling  (active)
    # -----------------------------------------------------------------------

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

    # -----------------------------------------------------------------------
    # Stage 3: Recommendation Engine  (TODO)
    # -----------------------------------------------------------------------

    def run_stage3(
        self,
        user_embedding: np.ndarray,
        tagged_places:  list[PlaceRecord],
        trip_context:   dict,
    ) -> list[PlaceRecord]:
        raise NotImplementedError("Stage 3 not yet implemented.")

    # -----------------------------------------------------------------------
    # Stage 4: Route / Itinerary Optimization  (TODO)
    # -----------------------------------------------------------------------

    def run_stage4(
        self,
        ranked_places: list[PlaceRecord],
        trip_context:  dict,
    ) -> list[dict]:
        raise NotImplementedError("Stage 4 not yet implemented.")

    # -----------------------------------------------------------------------
    # Persistence
    # -----------------------------------------------------------------------

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
