import os
import logging
from contextlib import asynccontextmanager

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ml.api.routes.recommend import router as recommend_router
from ml.api.routes.profile   import router as profile_router
from ml.api.routes.places    import router as places_router
from ml.pipeline import MLPipeline

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

ML_PORT = int(os.getenv("ML_PORT", "8001"))
ML_HOST = os.getenv("ML_HOST", "0.0.0.0")


def _normalize_preference(row: dict) -> dict:
    # DB column cuisines_preferences → ML field cuisine_preferences
    return {
        "user_id":              str(row.get("user_id", "")),
        "use_case":             row.get("use_case", ""),
        "party_type":           row.get("party_type", ""),
        "daily_budget_tier":    row.get("daily_budget_tier"),
        "trip_budget_tier":     row.get("trip_budget_tier"),
        "preferred_tags":       row.get("preferred_tags") or [],
        "exploration_score":    row.get("exploration_score"),
        "popularity_weight":    row.get("popularity_weight"),
        "cuisine_preferences":  row.get("cuisines_preferences") or [],
        "dietary_restrictions": row.get("dietary_restrictions") or [],
        "travel_mode":          row.get("travel_mode") or [],
        "max_travel_minutes":   row.get("max_travel_minutes", ""),
        "itinerary_pace":       row.get("itinerary_pace", "balanced"),
    }


def _ratings_to_visits(ratings: list[dict]) -> list[dict]:
    visits = []
    for row in ratings:
        user_id  = str(row.get("user_id", ""))
        place_id = str(row.get("place_id", ""))
        rating   = row.get("rating")
        if not user_id or not place_id or rating is None:
            continue
        visits.append({
            "user_id":     user_id,
            "place_id":    place_id,
            "rating":      float(rating),
            "visit_count": 1,
            "tags":        [],
        })
    return visits


@asynccontextmanager
async def lifespan(app: FastAPI):
    from pathlib import Path
    from ml.pipeline import PipelineConfig
    from ml.models.user_profiler import MIN_SVD_USERS

    artifact_path = os.getenv("PROFILER_ARTIFACT", "artifacts/user_profiler.joblib")

    if Path(artifact_path).exists():
        pipeline = MLPipeline.load(PipelineConfig(profiler_path=artifact_path))
        logger.info("Loaded pre-trained profiler from %s", artifact_path)
    else:
        pipeline = MLPipeline()
        logger.warning("No pre-trained artifact at %s — starting cold.", artifact_path)

    try:
        from supabase import create_client
        sb = create_client(os.getenv("SUPABASE_URL", ""), os.getenv("SUPABASE_KEY", ""))

        raw_prefs    = sb.table("preference").select("*").execute().data or []
        interactions = sb.table("user_interactions").select("*").execute().data or []
        raw_ratings  = sb.table("rating").select("*").execute().data or []

        prefs           = [_normalize_preference(p) for p in raw_prefs]
        implicit_visits = []
        if interactions:
            from ml.models.user_profiler import parse_app_interactions
            implicit_visits = parse_app_interactions(interactions, user_id=None)
        explicit_visits = _ratings_to_visits(raw_ratings)
        real_visits     = explicit_visits + implicit_visits

        real_interaction_users = len({v["user_id"] for v in real_visits})

        if real_interaction_users >= MIN_SVD_USERS:
            # enough real users to replace the Foursquare pre-training
            logger.info("%d real interaction users — retraining CF on live data.", real_interaction_users)
            pipeline.train_stage2(visits=real_visits, preferences=prefs)
        elif prefs:
            pipeline.train_stage2(visits=real_visits, preferences=prefs)
            logger.info("Pipeline updated: %d preferences, %d real interactions.", len(prefs), len(real_visits))
        else:
            logger.warning("No preference data in Supabase — running in content-only mode.")

    except Exception as e:
        logger.warning("Startup training failed (%s) — pipeline will use cold-start mode.", e, exc_info=True)

    app.state.pipeline = pipeline
    logger.info("ML pipeline ready.")
    yield


app = FastAPI(
    title="PlanIt ML Service",
    description="Recommendation engine for PlanIt — stages 1–3 of the ML pipeline.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(recommend_router)
app.include_router(profile_router)
app.include_router(places_router)


@app.get("/health")
def health():
    pipeline_ready = hasattr(app.state, "pipeline") and app.state.pipeline is not None
    return {"status": "ok", "pipeline_loaded": pipeline_ready}


if __name__ == "__main__":
    uvicorn.run(app, host=ML_HOST, port=ML_PORT)
