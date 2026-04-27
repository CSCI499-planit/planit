"""
    interaction feedback route — logs likes/dislikes on places and itineraries
"""
from fastapi import APIRouter, HTTPException, Depends
from postgrest.exceptions import APIError
from supabase import Client
from pydantic import BaseModel
from server.config.db import get_db_client, get_current_user
from server.controllers.interactions import log_interaction, EVENT_RATINGS

router = APIRouter(prefix="/interactions", tags=["interactions"])


class InteractionInput(BaseModel):
    place_id: str
    event_type: str  # like | unlike | itinerary_like | itinerary_dislike


@router.post("/")
async def post_interaction(
    data: InteractionInput,
    user=Depends(get_current_user),
    client: Client = Depends(get_db_client),
):
    if data.event_type not in EVENT_RATINGS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid event_type. Must be one of: {list(EVENT_RATINGS)}",
        )
    try:
        log_interaction(str(user.user.id), data.place_id, data.event_type, client=client)
        return {"status": "success"}
    except APIError as e:
        raise HTTPException(status_code=400, detail=str(e.message))


@router.get("/")
async def get_interactions(
    user=Depends(get_current_user),
    client: Client = Depends(get_db_client),
):
    try:
        response = (
            client.table("user_interactions")
            .select("*")
            .eq("user_id", str(user.user.id))
            .execute()
        )
        return {"status": "success", "data": response.data}
    except APIError as e:
        raise HTTPException(status_code=400, detail=str(e.message))
