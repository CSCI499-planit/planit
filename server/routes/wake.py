"""
 warmup route for Render free-tier services.
"""
import logging
import os
import time

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends
from supabase import Client

from server.config.db import get_current_user, get_db_client

logger = logging.getLogger(__name__)

ML_SERVICE_URL = os.getenv(
    "ML_SERVICE_URL", "http://localhost:8001").rstrip("/")
ML_INTERNAL_TOKEN = os.getenv("ML_INTERNAL_TOKEN", "").strip()
WAKE_COOLDOWN_SECONDS = int(os.getenv("WAKE_COOLDOWN_SECONDS", "60"))
_last_ml_wake_at = 0.0

router = APIRouter(prefix="/wake", tags=["wake"])


def _wake_ml_service(force: bool = False) -> None:
    global _last_ml_wake_at

    now = time.monotonic()
    if not force and now - _last_ml_wake_at < WAKE_COOLDOWN_SECONDS:
        return

    try:
        headers = (
            {"X-PlanIt-Internal-Token": ML_INTERNAL_TOKEN}
            if ML_INTERNAL_TOKEN else {}
        )
        res = httpx.get(f"{ML_SERVICE_URL}/health", headers=headers, timeout=45.0)
        res.raise_for_status()
        _last_ml_wake_at = now
    except Exception as exc:
        logger.warning("ML wakeup failed: %s", exc)


def _warm_user_data(user_id: str, client: Client) -> None:
    try:
        client.table("preference").select(
            "*").eq("user_id", user_id).limit(1).execute()
        client.table("user_interactions").select(
            "place_id, event_type, created_at").eq("user_id", user_id).execute()
        client.table("recommendation_logs").select("place_id").eq(
            "user_id", user_id).limit(100).execute()
    except Exception as exc:
        logger.warning("User data warmup failed for %s: %s", user_id, exc)


def _warm_session(user_id: str, client: Client) -> None:
    _wake_ml_service(force=True)
    _warm_user_data(user_id, client)


@router.get("")
async def wake_services(background_tasks: BackgroundTasks):
    background_tasks.add_task(_wake_ml_service)
    return {"status": "warming", "services": ["ml"]}


@router.get("/session")
async def wake_session(
    background_tasks: BackgroundTasks,
    user=Depends(get_current_user),
    client: Client = Depends(get_db_client),
):
    user_id = str(user.user.id)
    background_tasks.add_task(_warm_session, user_id, client)
    return {"status": "warming", "services": ["ml", "user_data"]}
