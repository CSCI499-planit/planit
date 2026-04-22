import asyncio
import os
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import uvicorn
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
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

# retrain fires when this many new interactions have accumulated AND the cooldown has passed
RETRAIN_THRESHOLD      = int(os.getenv("RETRAIN_THRESHOLD", "10"))
MIN_RETRAIN_INTERVAL_H = float(os.getenv("MIN_RETRAIN_INTERVAL_HOURS", "1"))
_WEBHOOK_SECRET        = os.getenv("WEBHOOK_SECRET", "")


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


def _cooldown_elapsed(last_retrain_at: datetime | None) -> bool:
    if last_retrain_at is None:
        return True
    elapsed_h = (datetime.now(timezone.utc) - last_retrain_at).total_seconds() / 3600
    return elapsed_h >= MIN_RETRAIN_INTERVAL_H


async def _do_retrain() -> None:
    # background retrain — acquires lock, swaps pipeline, updates timestamp
    async with app.state.retrain_lock:
        try:
            new_pipeline = await asyncio.to_thread(_fetch_and_train, app.state.pipeline)
            app.state.pipeline        = new_pipeline
            app.state.last_retrain_at = datetime.now(timezone.utc)
            logger.info("Background retrain completed.")
        except Exception as e:
            logger.error("Background retrain failed: %s", e, exc_info=True)


def _fetch_and_train(pipeline: MLPipeline) -> MLPipeline:
    # pulls latest data from Supabase and retrains stage 2 in-place
    from ml.models.user_profiler import MIN_SVD_USERS, parse_app_interactions
    from supabase import create_client

    sb = create_client(os.getenv("SUPABASE_URL", ""), os.getenv("SUPABASE_KEY", ""))

    raw_prefs    = sb.table("preference").select("*").execute().data or []
    interactions = sb.table("user_interactions").select("*").execute().data or []
    raw_ratings  = sb.table("rating").select("*").execute().data or []

    prefs           = [_normalize_preference(p) for p in raw_prefs]
    implicit_visits = parse_app_interactions(interactions) if interactions else []
    real_visits     = _ratings_to_visits(raw_ratings) + implicit_visits

    n_users = len({v["user_id"] for v in real_visits})
    if n_users >= MIN_SVD_USERS:
        logger.info("%d interaction users — retraining CF on live data.", n_users)
    elif prefs:
        logger.info("Fewer than %d interaction users — content-only mode.", MIN_SVD_USERS)
    else:
        logger.warning("No preference data in Supabase — cold-start mode.")

    if prefs:
        pipeline.train_stage2(visits=real_visits, preferences=prefs)
        pipeline.save()

    return pipeline


@asynccontextmanager
async def lifespan(app: FastAPI):
    from pathlib import Path
    from ml.pipeline import PipelineConfig

    artifact_path = os.getenv("PROFILER_ARTIFACT", "artifacts/user_profiler.joblib")

    if Path(artifact_path).exists():
        pipeline = MLPipeline.load(PipelineConfig(profiler_path=artifact_path))
        logger.info("Loaded pre-trained profiler from %s", artifact_path)
    else:
        pipeline = MLPipeline()
        logger.warning("No pre-trained artifact at %s — starting cold.", artifact_path)

    try:
        pipeline = await asyncio.to_thread(_fetch_and_train, pipeline)
    except Exception as e:
        logger.warning("Startup training failed (%s) — using loaded artifact.", e, exc_info=True)

    app.state.pipeline             = pipeline
    app.state.retrain_lock         = asyncio.Lock()
    app.state.pending_interactions = 0
    app.state.last_retrain_at      = datetime.now(timezone.utc)
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


@app.post("/webhook/interactions")
async def webhook_interactions(request: Request, background_tasks: BackgroundTasks):
    # called by Supabase database webhook on every user_interactions INSERT
    if _WEBHOOK_SECRET:
        auth = request.headers.get("authorization", "")
        if auth != f"Bearer {_WEBHOOK_SECRET}":
            raise HTTPException(status_code=401, detail="Invalid webhook secret.")

    app.state.pending_interactions += 1
    pending = app.state.pending_interactions

    should_retrain = (
        pending >= RETRAIN_THRESHOLD
        and not app.state.retrain_lock.locked()
        and _cooldown_elapsed(app.state.last_retrain_at)
    )

    if should_retrain:
        app.state.pending_interactions = 0
        background_tasks.add_task(_do_retrain)
        logger.info("Retrain scheduled after %d new interactions.", pending)

    return {"status": "ok", "pending": app.state.pending_interactions, "retrain_scheduled": should_retrain}


@app.post("/admin/retrain")
async def retrain():
    # manual hot-swap — lock prevents overlapping retrain jobs
    if app.state.retrain_lock.locked():
        raise HTTPException(status_code=409, detail="Retrain already in progress.")
    async with app.state.retrain_lock:
        try:
            new_pipeline = await asyncio.to_thread(_fetch_and_train, app.state.pipeline)
            app.state.pipeline        = new_pipeline
            app.state.last_retrain_at = datetime.now(timezone.utc)
            return {"status": "ok", "detail": "Pipeline retrained and swapped."}
        except Exception as e:
            logger.error("Retrain failed: %s", e, exc_info=True)
            raise HTTPException(status_code=500, detail=f"Retrain failed: {e}")


if __name__ == "__main__":
    uvicorn.run(app, host=ML_HOST, port=ML_PORT)
