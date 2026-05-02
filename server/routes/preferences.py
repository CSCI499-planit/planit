"""
    user preference route to store user preferences survey input
"""
import os
import logging

import httpx
from fastapi import APIRouter, HTTPException, Depends
from postgrest.exceptions import APIError
from supabase import Client

from server.config.db import get_db_client, get_current_user
from server.models.preferences import preferenceInput

logger = logging.getLogger(__name__)

PREFERENCE_TABLE = 'preference'
ML_SERVICE_URL   = os.getenv("ML_SERVICE_URL", "http://localhost:8001")

router = APIRouter(prefix="/preference", tags=["preference"])


def _ml_embed(preference: dict) -> dict | None:
    """Fire-and-forget embed call to ML. Returns result or None if ML is unavailable."""
    ml_pref = {**preference}
    # DB column is 'cuisines_preferences'; ML expects 'cuisine_preferences'
    if "cuisines_preferences" in ml_pref:
        ml_pref["cuisine_preferences"] = ml_pref.pop("cuisines_preferences")
    try:
        res = httpx.post(
            f"{ML_SERVICE_URL}/profile/embed",
            json={"preference": ml_pref, "visits": None},
            timeout=15.0,
        )
        res.raise_for_status()
        return res.json()
    except Exception as e:
        logger.warning("ML embed call failed (non-fatal): %s", e)
        return None


@router.post("/")
async def post_preference(data: preferenceInput, user=Depends(get_current_user), client: Client = Depends(get_db_client)):
    try:
        preference = data.model_dump()
        preference["user_id"] = str(user.user.id)
        response = client.table(PREFERENCE_TABLE).insert(preference).execute()
    except APIError as e:
        raise HTTPException(status_code=400, detail=str(e.message))

    embed_result = _ml_embed(preference)
    return {"status": "success", "data": response.data, "embedding": embed_result}


@router.get("/")
async def get_preference(client: Client = Depends(get_db_client), user=Depends(get_current_user)):
    try:
        response = (
            client.table(PREFERENCE_TABLE)
            .select('*')
            .eq('user_id', user.user.id)
            .execute()
        )
        return {"status": "success", "data": response.data}
    except APIError as e:
        raise HTTPException(status_code=400, detail=str(e.message))


@router.put("/")
async def update_preference(data: preferenceInput, client: Client = Depends(get_db_client), user=Depends(get_current_user)):
    try:
        preference = data.model_dump()
        response = (
            client.table(PREFERENCE_TABLE)
            .update(preference)
            .eq('user_id', user.user.id)
            .execute()
        )
        return {"status": "success", "data": response.data}
    except APIError as e:
        raise HTTPException(status_code=400, detail=str(e.message))


@router.delete("/")
async def delete_preference(client: Client = Depends(get_db_client), user=Depends(get_current_user)):
    try:
        response = (
            client.table(PREFERENCE_TABLE)
            .delete()
            .eq('user_id', user.user.id)
            .execute()
        )
        return {"status": "success", "data": response.data}
    except APIError as e:
        raise HTTPException(status_code=400, detail=str(e.message))
