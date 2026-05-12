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


_STORAGE_BUCKET   = os.getenv("ARTIFACT_BUCKET", "ml-artifacts")
_STORAGE_ARTIFACT = "user_profiler.joblib"


def _sb_service_client():
    from supabase import create_client
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY", "")
    return create_client(os.getenv("SUPABASE_URL", ""), key)


def _download_artifact(local_path: str) -> bool:
    try:
        sb   = _sb_service_client()
        data = sb.storage.from_(_STORAGE_BUCKET).download(_STORAGE_ARTIFACT)
        from pathlib import Path
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)
        Path(local_path).write_bytes(data)
        logger.info("Artifact downloaded from Supabase Storage → %s", local_path)
        return True
    except Exception as e:
        logger.warning("Artifact download failed: %s", e)
        return False


def _upload_artifact(local_path: str) -> None:
    try:
        from pathlib import Path
        sb   = _sb_service_client()
        data = Path(local_path).read_bytes()
        sb.storage.from_(_STORAGE_BUCKET).upload(
            _STORAGE_ARTIFACT, data,
            {"content-type": "application/octet-stream", "upsert": "true"},
        )
        logger.info("Artifact uploaded to Supabase Storage.")
    except Exception as e:
        logger.warning("Artifact upload failed: %s", e)


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


def _build_place_tag_db(rows: list[dict]) -> dict[str, list[str]]:
    from ml.models.place_classifier import rule_based_labels
    from ml.utilities.geoapify import normalize_db_place

    tag_db: dict[str, list[str]] = {}
    for row in rows:
        place_id = str(row.get("id") or row.get("place_id") or "")
        if not place_id:
            continue
        tags = row.get("tags") or []
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",") if t.strip()]
        if not tags:
            place = normalize_db_place(row) if "lat" in row else row
            if isinstance(place.get("hours"), dict):
                place = {**place, "hours": None}
            tags = [tag for tag, val in rule_based_labels(place).items() if val == 1]
        if tags:
            tag_db[place_id] = list(tags)
    return tag_db


def _ratings_to_visits(ratings: list[dict], place_tag_db: dict[str, list[str]]) -> list[dict]:
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
            "tags":        place_tag_db.get(place_id, []),
            "created_at":  row.get("created_at"),
        })
    return visits


def _impression_visits(rec_logs: list[dict], positive_keys: set[tuple[str, str]]) -> list[dict]:
    # shown-but-not-positively-interacted → weak implicit negative (rating 2.0)
    # only top-5 ranked positions: lower ranks may not have been seen by the user
    visits = []
    seen: set[tuple[str, str]] = set()
    for row in rec_logs:
        uid = str(row.get("user_id", ""))
        pid = str(row.get("place_id", ""))
        if not uid or not pid:
            continue
        if row.get("rank_position", 99) > 4:
            continue
        key = (uid, pid)
        if key in positive_keys or key in seen:
            continue
        seen.add(key)
        visits.append({
            "user_id":     uid,
            "place_id":    pid,
            "rating":      2.0,
            "visit_count": 1,
            "tags":        [],
            "created_at":  row.get("created_at"),
        })
    return visits


def _paginate_table(sb, table: str, page_size: int = 1000) -> list[dict]:
    # Supabase PostgREST default limit is 1000 rows; page through until exhausted
    rows: list[dict] = []
    offset = 0
    while True:
        batch = (
            sb.table(table)
            .select("*")
            .range(offset, offset + page_size - 1)
            .execute()
            .data or []
        )
        rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size
    return rows


def _count_interactions_since(since: datetime | None) -> int:
    sb = _sb_service_client()
    q = sb.table("user_interactions").select("id", count="exact")  # type: ignore[call-overload]
    if since:
        q = q.gte("created_at", since.isoformat())
    result = q.execute()
    return result.count if result.count is not None else len(result.data or [])


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
            app.state.place_tag_db    = new_pipeline.user_profiler.place_tag_db
            app.state.last_retrain_at = datetime.now(timezone.utc)
            logger.info("Background retrain completed.")
        except Exception as e:
            logger.error("Background retrain failed: %s", e, exc_info=True)


def _fetch_and_train(pipeline: MLPipeline) -> MLPipeline:
    # pulls latest data from Supabase and retrains stage 2 in-place
    from ml.models.user_profiler import MIN_SVD_USERS, parse_app_interactions

    sb = _sb_service_client()

    raw_prefs    = _paginate_table(sb, "preference")
    interactions = _paginate_table(sb, "user_interactions")
    raw_ratings  = _paginate_table(sb, "rating")
    try:
        raw_places = _paginate_table(sb, "place")
    except Exception as e:
        logger.warning("place tag lookup failed: %s", e)
        raw_places = []

    # Seed from the inference-time cache (populated by run_stage1 on every
    # recommendation call), then layer in any place-table rows on top.
    # This is the primary source of truth since the place table is empty —
    # Geoapify places are fetched per-request and never written to Supabase.
    place_tag_db = dict(pipeline.place_tag_db)
    place_tag_db.update(_build_place_tag_db(raw_places))

    prefs           = [_normalize_preference(p) for p in raw_prefs]
    implicit_visits = parse_app_interactions(interactions, place_tag_db=place_tag_db) if interactions else []
    real_visits     = _ratings_to_visits(raw_ratings, place_tag_db) + implicit_visits
    tagged_visits   = [v for v in real_visits if v.get("tags")]

    try:
        rec_logs = _paginate_table(sb, "recommendation_logs")
        positive_keys = {(v["user_id"], v["place_id"]) for v in real_visits if float(v.get("rating") or 0) >= 3.5}
        impression_negs = _impression_visits(rec_logs, positive_keys)
        for v in impression_negs:
            v["tags"] = place_tag_db.get(v["place_id"], [])
        tagged_visits += [v for v in impression_negs if v.get("tags")]
        logger.info("Added %d impression-negative visits from recommendation_logs.", len(impression_negs))
    except Exception as e:
        logger.warning("recommendation_logs fetch failed: %s", e)

    logger.info("place_tag_db has %d entries after merge.", len(place_tag_db))
    # Write back the merged cache so it's included in the saved artifact
    pipeline.place_tag_db = place_tag_db

    n_users = len({v["user_id"] for v in tagged_visits})
    if n_users >= MIN_SVD_USERS:
        logger.info("%d interaction users — retraining CF on live data.", n_users)
    elif prefs:
        logger.info("Fewer than %d interaction users — content-only mode.", MIN_SVD_USERS)
    else:
        logger.warning("No preference data in Supabase — cold-start mode.")

    # Compute per-place interaction counts as a popularity proxy.
    # Geoapify free tier never returns rating/review_count, so pop_score is
    # permanently 0 without this. Counts reflect real user engagement.
    from collections import Counter
    interaction_counts = dict(Counter(
        str(row.get("place_id", ""))
        for row in interactions
        if row.get("place_id")
    ))
    pipeline._recommender.interaction_counts = interaction_counts
    logger.info("interaction_counts: %d unique places.", len(interaction_counts))

    if prefs:
        pipeline.train_stage2(visits=tagged_visits, preferences=prefs)
        pipeline.save()
        _upload_artifact(pipeline.config.profiler_path)

    return pipeline


@asynccontextmanager
async def lifespan(app: FastAPI):
    from pathlib import Path
    from ml.pipeline import PipelineConfig

    artifact_path = os.getenv("PROFILER_ARTIFACT", "artifacts/user_profiler.joblib")

    if not Path(artifact_path).exists():
        _download_artifact(artifact_path)

    if Path(artifact_path).exists():
        pipeline = MLPipeline.load(PipelineConfig(profiler_path=artifact_path))
        logger.info("Loaded pre-trained profiler from %s", artifact_path)
    else:
        pipeline = MLPipeline()
        logger.warning("No artifact available — starting cold.")

    try:
        pipeline = await asyncio.to_thread(_fetch_and_train, pipeline)
    except Exception as e:
        logger.warning("Startup training failed (%s) — using loaded artifact.", e, exc_info=True)

    app.state.pipeline        = pipeline
    app.state.place_tag_db    = pipeline.user_profiler.place_tag_db
    app.state.retrain_lock    = asyncio.Lock()
    app.state.last_retrain_at = datetime.now(timezone.utc)
    logger.info("ML pipeline ready. place_tag_db has %d entries.", len(app.state.place_tag_db))

    asyncio.create_task(_persist_tag_db(app))
    yield


async def _persist_tag_db(app: FastAPI) -> None:
    """Periodically save the artifact when run_stage1 has grown place_tag_db.

    run_stage1 accumulates {place_id: tags} in memory on every recommendation
    request, but pipeline.save() only runs during _fetch_and_train(). On Render
    free tier the service restarts before enough interactions trigger a retrain,
    so the tag cache is lost. This task saves the artifact every 5 minutes when
    the cache has grown, keeping it fresh across restarts.
    """
    last_saved_size = len(app.state.pipeline.place_tag_db)
    while True:
        await asyncio.sleep(300)  # 5-minute cadence
        try:
            pipeline = app.state.pipeline
            current_size = len(pipeline.place_tag_db)
            if current_size > last_saved_size + 4:  # at least 5 new entries
                logger.info(
                    "place_tag_db grew %d → %d — persisting artifact.",
                    last_saved_size, current_size,
                )
                await asyncio.to_thread(pipeline.save)
                await asyncio.to_thread(_upload_artifact, pipeline.config.profiler_path)
                last_saved_size = current_size
        except Exception as e:
            logger.warning("place_tag_db persister error: %s", e)


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

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=[
#         "http://localhost:5174",
#         "http://localhost:5173",
#     ],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

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

    # fast-path: skip DB query when lock is held or cooldown hasn't elapsed
    if app.state.retrain_lock.locked() or not _cooldown_elapsed(app.state.last_retrain_at):
        return {"status": "ok", "retrain_scheduled": False}

    # DB-backed count so restarts don't lose accumulated interactions
    pending = await asyncio.to_thread(_count_interactions_since, app.state.last_retrain_at)
    should_retrain = pending >= RETRAIN_THRESHOLD

    if should_retrain:
        background_tasks.add_task(_do_retrain)
        logger.info("Retrain scheduled after %d new interactions.", pending)

    return {"status": "ok", "pending": pending, "retrain_scheduled": should_retrain}


@app.post("/admin/retrain", status_code=202)
async def retrain(background_tasks: BackgroundTasks):
    # Schedules a hot-swap retrain in the background and returns immediately.
    # The 202 response means "accepted" — use /health to confirm the swap landed.
    if app.state.retrain_lock.locked():
        raise HTTPException(status_code=409, detail="Retrain already in progress.")
    background_tasks.add_task(_do_retrain)
    return {"status": "accepted", "detail": "Retrain scheduled."}


if __name__ == "__main__":
    uvicorn.run(app, host=ML_HOST, port=ML_PORT)
