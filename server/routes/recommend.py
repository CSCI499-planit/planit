"""
    Recommendation and itinerary routes.
    Proxies requests to the ML service and returns the results.
"""
import os
import httpx
from fastapi import APIRouter, Depends, HTTPException
from supabase import Client
from server.config.db import get_current_user, get_db_client
from server.controllers.interactions import EVENT_RATINGS

router = APIRouter(prefix="/recommend", tags=["recommend"])

ML_SERVICE_URL = os.getenv("ML_SERVICE_URL", "http://localhost:8001")

_NEGATIVE_EVENTS = {"unlike", "itinerary_dislike"}


def _ml_post(path: str, body: dict) -> dict:
    try:
        res = httpx.post(
            f"{ML_SERVICE_URL}{path}",
            json=body,
            timeout=30.0,
        )
        res.raise_for_status()
        return res.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="ML service timed out.")
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="ML service is unavailable.")


def _fetch_user_history(user_id: str, client: Client) -> tuple[list[dict], list[str]]:
    """Returns (visits, excluded_place_ids) built from the user's interaction + rating history."""
    interactions = (
        client.table("user_interactions")
        .select("place_id, event_type, created_at")
        .eq("user_id", user_id)
        .execute()
        .data or []
    )
    ratings = (
        client.table("rating")
        .select("place_id, rating, created_at")
        .eq("user_id", user_id)
        .execute()
        .data or []
    )

    excluded: list[str] = [
        row["place_id"] for row in interactions
        if row.get("event_type") in _NEGATIVE_EVENTS
    ]

    # aggregate interactions per place (avg implicit rating)
    agg: dict[str, dict] = {}
    for row in interactions:
        pid   = row["place_id"]
        event = row.get("event_type", "")
        r     = EVENT_RATINGS.get(event, 2.5)
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

    # merge explicit ratings (overwrite implicit if both exist)
    rating_map = {row["place_id"]: row for row in ratings}
    seen_pids  = {v["place_id"] for v in visits}
    for pid, row in rating_map.items():
        if pid in seen_pids:
            for v in visits:
                if v["place_id"] == pid:
                    v["rating"] = float(row["rating"])
                    break
        else:
            visits.append({
                "user_id":     user_id,
                "place_id":    pid,
                "rating":      float(row["rating"]),
                "visit_count": 1,
                "tags":        [],
                "created_at":  row.get("created_at"),
            })

    return visits, excluded


@router.post("/places")
async def recommend_places(body: dict, user=Depends(get_current_user), client: Client = Depends(get_db_client)):
    user_id = str(user.user.id)
    body["preference"]["user_id"] = user_id

    visits, excluded = _fetch_user_history(user_id, client)
    body["visits"]              = visits
    body["excluded_place_ids"]  = excluded

    return _ml_post("/recommend", body)


@router.post("/itinerary")
async def recommend_itinerary(body: dict, user=Depends(get_current_user), client: Client = Depends(get_db_client)):
    user_id = str(user.user.id)
    body["preference"]["user_id"] = user_id

    visits, excluded = _fetch_user_history(user_id, client)
    body["visits"]             = visits
    body["excluded_place_ids"] = excluded

    return _ml_post("/itinerary", body)
