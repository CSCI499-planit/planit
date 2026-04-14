"""
    Recommendation and itinerary routes.
    Proxies requests to the ML service and returns the results.
"""
import os
import httpx
from fastapi import APIRouter, Depends, HTTPException
from server.config.db import get_current_user

router = APIRouter(prefix="/recommend", tags=["recommend"])

ML_SERVICE_URL = os.getenv("ML_SERVICE_URL", "http://localhost:8001")


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


@router.post("/places")
async def recommend_places(body: dict, user=Depends(get_current_user)):
    """
    Get ranked place recommendations for a user.

    Body mirrors the ML service's RecommendRequest:
    {
        "preference": { ...user survey fields... },
        "places":     [ ...PlaceRecord list... ],
        "visits":     [ ...optional UserVisit list... ],
        "top_k":      20
    }
    """
    body["preference"]["user_id"] = str(user.user.id)
    return _ml_post("/recommend", body)


@router.post("/itinerary")
async def recommend_itinerary(body: dict, user=Depends(get_current_user)):
    """
    Get a day-by-day itinerary (stages 1–4) for a user.

    Body mirrors the ML service's ItineraryRequest:
    {
        "preference": { ...user survey fields... },
        "places":     [ ...PlaceRecord list... ],
        "visits":     [ ...optional UserVisit list... ],
        "trip_days":  1,
        "start_date": "2026-04-14"
    }
    """
    body["preference"]["user_id"] = str(user.user.id)
    return _ml_post("/itinerary", body)
