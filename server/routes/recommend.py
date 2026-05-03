"""
    Recommendation and itinerary routes.

    Single-call endpoints: the frontend only needs a location string.
    The server handles fetching places from the ML service, loading the
    user's saved preference, injecting interaction history, and proxying
    to the ML recommendation/itinerary endpoints.
"""
import os
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from supabase import Client

from server.config.db import get_current_user, get_db_client
from server.controllers.interactions import EVENT_RATINGS

router = APIRouter(prefix="/recommend", tags=["recommend"])

ML_SERVICE_URL = os.getenv("ML_SERVICE_URL", "http://localhost:8001")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _ml_get(path: str, params: dict) -> dict:
    try:
        res = httpx.get(f"{ML_SERVICE_URL}{path}", params=params, timeout=90.0)
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
        res = httpx.post(f"{ML_SERVICE_URL}{path}", json=body, timeout=60.0)
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
        .select("place_id, event_type, created_at")
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
        if event == "google_import":
            r = float((row.get("metadata") or {}).get("rating", 3.0))
        else:
            r = EVENT_RATINGS.get(event, 2.5)
        if pid not in agg:
            agg[pid] = {"ratings": [], "visit_count": 0, "created_at": row.get("created_at")}
        agg[pid]["ratings"].append(r)
        agg[pid]["visit_count"] += 1

    visits: list[dict] = [
        {
            "user_id":     user_id,
            "place_id":    pid,
            "rating":      round(sum(v["ratings"]) / len(v["ratings"]), 2),
            "visit_count": v["visit_count"],
            "tags":        [],
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
        places = _fetch_places(location, radius_m, min(limit * 2, 200))
        fresh  = [p for p in places if p.get("place_id") not in excluded_set]

    if len(fresh) < fresh_target:
        # retry 2: double the limit AND expand radius by 50 %
        places = _fetch_places(location, int(radius_m * 1.5), min(limit * 2, 200))

    return places


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class PlacesRequest(BaseModel):
    location:  str
    top_k:     int = 20
    radius_m:  int = 5000
    limit:     int = 50


class HotelLocation(BaseModel):
    latitude:  float
    longitude: float


class ItineraryRequest(BaseModel):
    location:       str
    trip_days:      int = 1
    start_date:     Optional[str] = None
    hotel_location: Optional[HotelLocation] = None
    top_k:          int = 20
    radius_m:       int = 5000
    limit:          int = 50


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
    places           = _fetch_places_with_novelty(body.location, body.radius_m, body.limit, excluded, body.top_k)

    ml_body = {
        "preference":         preference,
        "places":             places,
        "visits":             visits,
        "excluded_place_ids": excluded,
        "top_k":              body.top_k,
    }
    return _ml_post("/recommend", ml_body)


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
    places           = _fetch_places_with_novelty(body.location, body.radius_m, body.limit, excluded, body.top_k)

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
    return _ml_post("/itinerary", ml_body)
