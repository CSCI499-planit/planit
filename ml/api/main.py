"""
    ML service entry point.
    Runs separately from server/main.py on its own port (default 8001).
    The main server calls this over HTTP whenever it needs recommendations.

    Start with: uvicorn ml.api.main:app --port 8001 --reload
"""

import os
import logging
from contextlib import asynccontextmanager

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ml.api.routes.recommend import router as recommend_router
from ml.api.routes.profile   import router as profile_router
from ml.pipeline import MLPipeline

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

ML_PORT = int(os.getenv("ML_PORT", "8001"))
ML_HOST = os.getenv("ML_HOST", "0.0.0.0")


def _normalize_preference(row: dict) -> dict:
    """
    Maps Supabase 'preference' table columns → ML pipeline field names.

    DB column         ML field
    ─────────────── → ──────────────────
    user_id (UUID)  → user_id (str)
    party_type      → party_type
    preferred_tags  → preferred_tags
    cuisines_prefs  → cuisine_preferences  (DB uses plural 'cuisines_')
    """
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
    """
    Converts rows from the 'rating' table → UserVisit records for CF training.
    Explicit 1–5 ratings are the strongest CF signal we have.
    """
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
    pipeline = MLPipeline()

    try:
        from supabase import create_client
        sb = create_client(os.getenv("SUPABASE_URL", ""), os.getenv("SUPABASE_KEY", ""))

        raw_prefs    = sb.table("preference").select("*").execute().data or []
        interactions = sb.table("user_interactions").select("*").execute().data or []
        raw_ratings  = sb.table("rating").select("*").execute().data or []

        prefs = [_normalize_preference(p) for p in raw_prefs]

        if prefs:
            from ml.models.user_profiler import parse_app_interactions
            implicit_visits = parse_app_interactions(interactions, user_id=None) if interactions else []
            explicit_visits = _ratings_to_visits(raw_ratings)
            visits = explicit_visits + implicit_visits
            pipeline.train_stage2(visits=visits, preferences=prefs)
            logger.info(
                "Pipeline trained on %d preferences, %d explicit ratings, %d implicit interactions.",
                len(prefs), len(explicit_visits), len(implicit_visits),
            )
        else:
            logger.warning("No preference data in Supabase — running in content-only mode.")

    except Exception as e:
        logger.warning("Startup training failed (%s) — pipeline will use cold-start mode.", e)

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
    allow_origins=["*"],   # tighten this in production to the main server's URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(recommend_router)
app.include_router(profile_router)


@app.get("/health")
def health():
    pipeline_ready = hasattr(app.state, "pipeline") and app.state.pipeline is not None
    return {"status": "ok", "pipeline_loaded": pipeline_ready}


if __name__ == "__main__":
    uvicorn.run(app, host=ML_HOST, port=ML_PORT)
