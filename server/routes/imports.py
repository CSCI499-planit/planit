"""
    Google Takeout import route.
    Accepts one or more JSON files from a Google Takeout export and stores
    them as interactions so they feed into future recommendations.
"""
import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from supabase import Client

from ml.data.google_takeout import (
    parse_google_takeout,
    parse_google_reviews,
    parse_google_saved_places,
)
from server.config.db import get_current_user, get_db_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/import", tags=["import"])

_BATCH_SIZE = 100


def _detect_file_type(data: Any) -> str | None:
    if isinstance(data, dict) and "timelineObjects" in data:
        return "timeline"
    if isinstance(data, dict) and "features" in data:
        first = (data["features"] or [{}])[0]
        if "five_star_rating_published" in first.get("properties", {}):
            return "reviews"
        return "saved"
    return None


def _bulk_insert(client: Client, rows: list[dict]) -> None:
    for i in range(0, len(rows), _BATCH_SIZE):
        client.table("user_interactions").insert(rows[i : i + _BATCH_SIZE]).execute()


@router.post("/google-takeout")
async def import_google_takeout(
    files: list[UploadFile],
    user=Depends(get_current_user),
    client: Client = Depends(get_db_client),
):
    """
    Accepts one or more Google Takeout JSON files:
      - Semantic Location History  (Timeline *.json)
      - Maps/Reviews.json
      - Maps/Saved Places.json

    Each file is auto-detected and parsed. Results are stored as
    'google_import' interactions so they improve future recommendations.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")

    user_id = str(user.user.id)
    source_counts = {"timeline": 0, "reviews": 0, "saved": 0}
    aggregated: dict[str, dict] = {}

    for file in files:
        raw = await file.read()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=400,
                detail=f"'{file.filename}' is not valid JSON.",
            )

        file_type = _detect_file_type(data)
        if file_type is None:
            raise HTTPException(
                status_code=400,
                detail=f"'{file.filename}' is not a recognised Google Takeout file.",
            )

        if file_type == "timeline":
            visits = parse_google_takeout(data, user_id, place_tag_db={})
            source = "timeline"
        elif file_type == "reviews":
            visits = parse_google_reviews(data, user_id)
            source = "reviews"
        else:
            visits = parse_google_saved_places(data, user_id)
            source = "saved"

        source_counts[source] += len(visits)

        # Deduplicate across files — keep the highest rating per place
        for v in visits:
            pid = v["place_id"]
            if pid not in aggregated or v["rating"] > aggregated[pid]["rating"]:
                aggregated[pid] = {**v, "source": source}

    if not aggregated:
        return {"imported": 0, "sources": source_counts}

    rows = [
        {
            "user_id":    user_id,
            "place_id":   v["place_id"],
            "event_type": "google_import",
            "metadata": {
                "rating":      v["rating"],
                "visit_count": v.get("visit_count", 1),
                "source":      v["source"],
                "tags":        v.get("tags", []),
            },
        }
        for v in aggregated.values()
    ]

    try:
        _bulk_insert(client, rows)
    except Exception as e:
        logger.error("Google Takeout import failed for user %s: %s", user_id, e)
        raise HTTPException(status_code=500, detail="Failed to save import data.")

    return {"imported": len(rows), "sources": source_counts}
