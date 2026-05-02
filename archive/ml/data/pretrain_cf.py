"""
One-time CF pre-training on Foursquare TIST 2015.

Ran locally before deploying to seed the collaborative filtering matrix
with real user behaviour. The resulting artifact (user_profiler.joblib) is committed to git so
Render never has to touch the raw Foursquare files.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import cast

from ml.data.preprocess import UserPreference

logging.basicConfig(level=logging.INFO,
                    format="%(levelname)s %(name)s — %(message)s")
logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[2]

FS_POI_PATH = Path(os.getenv("FS_POI_PATH",     _REPO_ROOT /
                   "data/foursquare/dataset_TIST2015_POIs.txt"))
FS_CHECKIN_PATH = Path(os.getenv(
    "FS_CHECKIN_PATH", _REPO_ROOT / "data/foursquare/dataset_TIST2015_Checkins.txt"))
ARTIFACT_PATH = Path(
    os.getenv("ARTIFACT_PATH",   _REPO_ROOT / "artifacts/user_profiler.joblib"))

MAX_FS_USERS = int(os.getenv("MAX_FS_USERS", "50000"))
MIN_CHECKINS = int(os.getenv("MIN_CHECKINS", "5"))


def _load_supabase_preferences() -> list[dict]:
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_KEY", "")
    if not url or not key:
        logger.warning("SUPABASE Errorr")
        return []
    try:
        from supabase import create_client
        sb = create_client(url, key)
        rows = sb.table("preference").select("*").execute().data or []
        logger.info("Loaded %d preferences from Supabase.", len(rows))
        return rows
    except Exception as e:
        logger.warning("Could not load Supabase preferences: %s", e)
        return []


def _normalize_preference(row: dict) -> UserPreference:
    return cast(UserPreference, {
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
    })


def main() -> None:
    from ml.data.preprocess import load_foursquare_pois, load_foursquare_checkins, UserPreference
    from ml.pipeline import MLPipeline

    if not (FS_POI_PATH.exists() and FS_CHECKIN_PATH.exists()):
        logger.error(
            "Foursquare files not found at %s. "
            "Download dataset_TIST2015_POIs.txt and dataset_TIST2015_Checkins.txt "
            "into data/foursquare/.",
            FS_POI_PATH.parent,
        )
        raise SystemExit(1)

    logger.info("Loading Foursquare POIs from %s …", FS_POI_PATH)
    fs_pois = load_foursquare_pois(FS_POI_PATH)
    venue_tag_map = {p.get("place_id", ""): (
        p.get("tags") or []) for p in fs_pois}
    logger.info("Loaded %d tagged Foursquare venues.", len(venue_tag_map))

    logger.info("Loading Foursquare check-ins (max_users=%d, min_checkins=%d) …",
                MAX_FS_USERS, MIN_CHECKINS)
    fs_visits = load_foursquare_checkins(
        FS_CHECKIN_PATH,
        venue_tag_map=venue_tag_map,
        min_checkins=MIN_CHECKINS,
        max_users=MAX_FS_USERS,
    )
    logger.info("Foursquare: %d user-venue visit pairs.", len(fs_visits))

    raw_prefs = _load_supabase_preferences()
    preferences = [_normalize_preference(r) for r in raw_prefs]
    if not preferences:
        logger.warning(
            "No survey preferences loaded — CF pre-training will run without them.")

    logger.info(
        "Pre-training on %d total visits, %d preferences …",
        len(fs_visits), len(preferences),
    )
    pipeline = MLPipeline()
    pipeline.train_stage2(visits=fs_visits, preferences=preferences)

    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    pipeline.user_profiler.save(ARTIFACT_PATH)
    logger.info("Pre-trained profiler saved to %s", ARTIFACT_PATH)


if __name__ == "__main__":
    main()
