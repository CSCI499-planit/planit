# Main interface for the ML pipeline.
# MLPipeline orchestrates all stages: classification, profiling, recommendation, and optimization.
# Backend calls stage methods without needing to know implementation details.


from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ml.data.preprocess import PlaceRecord
from ml.models.place_classifier import PlaceTagClassifier

logger = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    classifier_path:     str      = "artifacts/place_classifier.joblib"
    rf_n_estimators:     int      = 200
    rf_max_depth:        int | None = None
    rf_min_samples_leaf: int      = 5
    rf_random_state:     int      = 42
    user_embedding_dim:  int      = 64   # stage 2
    rec_top_k:           int      = 20   # stage 3
    max_places_per_day:  int      = 6    # stage 4
    travel_mode:         str      = "drive"  # "drive" | "walk" | "transit"


class MLPipeline:
    # Entry point for the backend. After loading, the backend calls:
    #   tagged_places = pipeline.run_stage1(places)
    # where `places` is a list of PlaceRecord dicts.

    def __init__(self, config: PipelineConfig | None = None) -> None:
        self.config = config or PipelineConfig()
        self.place_classifier = PlaceTagClassifier(
            n_estimators=self.config.rf_n_estimators,
            max_depth=self.config.rf_max_depth,
            min_samples_leaf=self.config.rf_min_samples_leaf,
            random_state=self.config.rf_random_state,
        )
        # stages 2-4 will be set when their models are built
        self._user_profiler:   Any = None
        self._recommender:     Any = None
        self._route_optimizer: Any = None

    # --- Stage 1: Place Classification & Tagging (WIP) ---

    def train_stage1(
        self,
        places: list[PlaceRecord],
        label_dicts: list[dict[str, int]] | None = None,
    ) -> None:
        # pass label_dicts=None to use rule-based auto-labelling (good for initial training)
        if label_dicts is None:
            self.place_classifier.train_from_auto_labels(places)
        else:
            self.place_classifier.train(places, label_dicts)

    def run_stage1(self, places: list[PlaceRecord]) -> list[PlaceRecord]:
        # returns new PlaceRecord dicts with "tags" field added
        logger.info("Stage 1: tagging %d places", len(places))
        return self.place_classifier.tag_places(places)

    # --- Stage 2: User Preference Profiling (stub) ---

    def run_stage2(self, user_id: str, survey_responses: dict) -> Any:
        raise NotImplementedError("Stage 2 not yet implemented.")

    # --- Stage 3: Recommendation Engine (stub) ---

    def run_stage3(
        self,
        user_embedding: Any,
        tagged_places: list[PlaceRecord],
        trip_context: dict,
    ) -> list[PlaceRecord]:
        raise NotImplementedError("Stage 3 not yet implemented.")

    # --- Stage 4: Route / Itinerary Optimization (stub) ---

    def run_stage4(self, ranked_places: list[PlaceRecord], trip_context: dict) -> list[dict]:
        raise NotImplementedError("Stage 4 not yet implemented.")

    # --- Persistence ---

    def save(self) -> None:
        self.place_classifier.save(self.config.classifier_path)

    @classmethod
    def load(cls, config: PipelineConfig | None = None) -> "MLPipeline":
        obj  = cls(config)
        path = obj.config.classifier_path
        if Path(path).exists():
            obj.place_classifier = PlaceTagClassifier.load(path)
        else:
            logger.warning("No saved classifier at %s — pipeline needs training.", path)
        return obj
