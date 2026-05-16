"""
    Recommendation and itinerary routes.

    Single-call endpoints: the frontend only needs a location string.
    The server handles fetching places from the ML service, loading the
    user's saved preference, injecting interaction history, and proxying
    to the ML recommendation/itinerary endpoints.
"""
import os
import logging
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from supabase import Client

from server.config.db import get_current_user, get_db_client
from server.controllers.interactions import EVENT_RATINGS

router = APIRouter(prefix="/recommend", tags=["recommend"])

ML_SERVICE_URL = os.getenv("ML_SERVICE_URL", "http://localhost:8001").rstrip("/")
ML_INTERNAL_TOKEN = os.getenv("ML_INTERNAL_TOKEN", "").strip()
MAX_PLACE_SEARCH_LIMIT = 100
MAX_RADIUS_M = 50_000
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _ml_headers() -> dict[str, str]:
    if not ML_INTERNAL_TOKEN:
        return {}
    return {"X-PlanIt-Internal-Token": ML_INTERNAL_TOKEN}


def _metadata_float(meta: dict, key: str, default: float) -> float:
    try:
        return float(meta.get(key, default))
    except (TypeError, ValueError):
        return default


def _metadata_int(meta: dict, key: str, default: int) -> int:
    try:
        return max(int(meta.get(key, default)), 1)
    except (TypeError, ValueError):
        return default


def _metadata_tags(meta: dict) -> list[str]:
    raw = meta.get("tags") or []
    if isinstance(raw, str):
        return [tag.strip() for tag in raw.split(",") if tag.strip()]
    if isinstance(raw, list):
        return [str(tag).strip() for tag in raw if str(tag).strip()]
    return []


def _ml_get(path: str, params: dict) -> dict:
    try:
        res = httpx.get(
            f"{ML_SERVICE_URL}{path}",
            params=params,
            headers=_ml_headers(),
            timeout=90.0,
        )
        res.raise_for_status()
        return res.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="ML service timed out.")
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="ML service is unavailable.")


def _ml_post(path: str, body: dict) -> dict:
    try:
        res = httpx.post(
            f"{ML_SERVICE_URL}{path}",
            json=body,
            headers=_ml_headers(),
            timeout=60.0,
        )
        res.raise_for_status()
        return res.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="ML service timed out.")
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="ML service is unavailable.")


def _fetch_user_preference(user_id: str, client: Client) -> dict:
    """Load the user's saved preference row from Supabase and normalise field names for ML."""
    rows = (
        client.table("preference")
        .select("*")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
        .data or []
    )
    if not rows:
        raise HTTPException(
            status_code=404,
            detail="User preference not found. Please complete the onboarding survey first.",
        )
    pref = rows[0]
    pref["user_id"] = user_id
    return pref


def _fetch_user_history(user_id: str, client: Client) -> tuple[list[dict], list[str]]:
    """Returns (visits, excluded_place_ids) built from the user's interaction history."""
    interactions = (
        client.table("user_interactions")
        .select("place_id, event_type, metadata, created_at")
        .eq("user_id", user_id)
        .execute()
        .data or []
    )
    # also exclude every place previously shown in recommendation_logs —
    # so repeated requests for the same location always surface new places
    shown = (
        client.table("recommendation_logs")
        .select("place_id")
        .eq("user_id", user_id)
        .execute()
        .data or []
    )

    excluded: list[str] = list(
        {row["place_id"] for row in interactions}
        | {row["place_id"] for row in shown}
    )

    agg: dict[str, dict] = {}
    for row in interactions:
        pid   = row["place_id"]
        event = row.get("event_type", "")
        meta  = row.get("metadata") or {}
        if event == "google_import":
            r = _metadata_float(meta, "rating", 3.0)
            visit_count = _metadata_int(meta, "visit_count", 1)
            tags = _metadata_tags(meta)
        else:
            r = EVENT_RATINGS.get(event, 2.5)
            visit_count = 1
            tags = []
        if pid not in agg:
            agg[pid] = {
                "ratings": [],
                "visit_count": 0,
                "tags": set(),
                "created_at": row.get("created_at"),
            }
        agg[pid]["ratings"].extend([r] * visit_count)
        agg[pid]["visit_count"] += visit_count
        agg[pid]["tags"].update(tags)

    visits: list[dict] = [
        {
            "user_id":     user_id,
            "place_id":    pid,
            "rating":      round(sum(v["ratings"]) / len(v["ratings"]), 2),
            "visit_count": v["visit_count"],
            "tags":        list(v["tags"]),
            "created_at":  v["created_at"],
        }
        for pid, v in agg.items()
    ]

    return visits, excluded


def _fetch_places(location: str, radius_m: int, limit: int) -> list[dict]:
    result = _ml_get("/places/search", {"location": location, "radius_m": radius_m, "limit": limit})
    places = result.get("places", [])
    if not places:
        raise HTTPException(status_code=404, detail=f"No places found near {location!r}.")
    return places


def _fetch_places_with_novelty(
    location: str,
    radius_m: int,
    limit: int,
    excluded: list[str],
    top_k: int,
) -> list[dict]:
    """
    Fetches places and checks how many are fresh (not in excluded).
    If fewer than 2 × top_k fresh places remain, retries with a higher limit,
    then a wider radius, so repeated requests always have enough new candidates.
    """
    excluded_set = set(excluded)
    fresh_target = top_k * 2

    places = _fetch_places(location, radius_m, limit)
    fresh  = [p for p in places if p.get("place_id") not in excluded_set]

    if len(fresh) < fresh_target:
        # retry 1: double the limit, same radius
        places = _fetch_places(location, radius_m, min(limit * 2, MAX_PLACE_SEARCH_LIMIT))
        fresh  = [p for p in places if p.get("place_id") not in excluded_set]

    if len(fresh) < fresh_target:
        # retry 2: double the limit AND expand radius by 50 %
        places = _fetch_places(
            location,
            min(int(radius_m * 1.5), MAX_RADIUS_M),
            min(limit * 2, MAX_PLACE_SEARCH_LIMIT),
        )
        fresh  = [p for p in places if p.get("place_id") not in excluded_set]

    return fresh


def _log_recommendation_impressions(
    user_id: str,
    places: list[dict],
    client: Client,
) -> None:
    if not places:
        return

    rows = [
        {
            "user_id":       user_id,
            "place_id":      place.get("place_id"),
            "rank_position": position,
            "features":      place.get("score_breakdown") or {},
            "final_score":   place.get("score", 0.0),
        }
        for position, place in enumerate(places)
        if place.get("place_id")
    ]
    if not rows:
        return

    try:
        client.table("recommendation_logs").insert(rows).execute()
    except Exception as exc:
        logger.warning("recommendation impression logging failed: %s", exc)


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class PlacesRequest(BaseModel):
    location:           str = Field(..., min_length=2, max_length=120)
    top_k:              int = Field(20, ge=1, le=50)
    radius_m:           int = Field(5000, ge=100, le=MAX_RADIUS_M)
    limit:              int = Field(50, ge=1, le=MAX_PLACE_SEARCH_LIMIT)
    excluded_place_ids: list[str] = Field(default_factory=list, max_length=500)


class HotelLocation(BaseModel):
    latitude:  float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


class ItineraryRequest(BaseModel):
    location:       str = Field(..., min_length=2, max_length=120)
    trip_days:      int = Field(1, ge=1, le=14)
    start_date:     Optional[str] = None
    hotel_location: Optional[HotelLocation] = None
    top_k:          int = Field(20, ge=1, le=50)
    radius_m:       int = Field(5000, ge=100, le=MAX_RADIUS_M)
    limit:          int = Field(50, ge=1, le=MAX_PLACE_SEARCH_LIMIT)
    excluded_place_ids: list[str] = Field(default_factory=list, max_length=500)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/places")
async def recommend_places(
    body: PlacesRequest,
    user=Depends(get_current_user),
    client: Client = Depends(get_db_client),
):
    """
    Accepts a location name and returns ML-ranked places personalised for the
    authenticated user.

    Frontend sends:  { location, top_k?, radius_m?, limit? }
    Server returns:  { places: [{name, address, score, score_breakdown, ...}] }
    """
    user_id = str(user.user.id)

    preference       = _fetch_user_preference(user_id, client)
    visits, excluded = _fetch_user_history(user_id, client)
    excluded = list(set(excluded) | set(body.excluded_place_ids))
    places           = _fetch_places_with_novelty(body.location, body.radius_m, body.limit, excluded, body.top_k)
    if not places:
        raise HTTPException(
            status_code=404,
            detail="No new places found for this destination. Try a nearby neighborhood or a wider destination.",
        )

    ml_body = {
        "preference":         preference,
        "places":             places,
        "visits":             visits,
        "excluded_place_ids": excluded,
        "top_k":              body.top_k,
    }
    result = _ml_post("/recommend", ml_body)
    _log_recommendation_impressions(
        user_id,
        result.get("places", []),
        client,
    )
    return result


@router.post("/itinerary")
async def recommend_itinerary(
    body: ItineraryRequest,
    user=Depends(get_current_user),
    client: Client = Depends(get_db_client),
):
    """
    Accepts a location name and returns a day-by-day itinerary personalised for
    the authenticated user. Number of stops per day is driven by the user's
    saved itinerary_pace preference (packed=6, balanced=4, relaxed=3).

    Frontend sends:  { location, trip_days?, start_date?, hotel_location?, top_k?, radius_m?, limit? }
    Server returns:  { itinerary: [{ day, date?, stops: [{place, arrival_time, departure_time, travel_to_next}] }] }
    """
    user_id = str(user.user.id)

    preference       = _fetch_user_preference(user_id, client)
    visits, excluded = _fetch_user_history(user_id, client)
    excluded = list(set(excluded) | set(body.excluded_place_ids))
    places           = _fetch_places_with_novelty(body.location, body.radius_m, body.limit, excluded, body.top_k)
    if not places:
        raise HTTPException(
            status_code=404,
            detail="No new places found for this destination. Try a nearby neighborhood or a wider destination.",
        )

    ml_body = {
        "preference":         preference,
        "places":             places,
        "visits":             visits,
        "excluded_place_ids": excluded,
        "top_k":              body.top_k,
        "trip_days":          body.trip_days,
        "start_date":         body.start_date,
        "hotel_location":     body.hotel_location.model_dump() if body.hotel_location else None,
    }
    result = _ml_post("/itinerary", ml_body)
    _log_recommendation_impressions(
        user_id,
        [
            stop.get("place", {})
            for day in result.get("itinerary", [])
            for stop in day.get("stops", [])
        ],
        client,
    )
    return result
