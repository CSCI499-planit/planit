"""
Presentation demo — Ahmed's user profile + 3 unlike users, 3 different locations, 1-day itinerary each.

Users chosen to be as different as possible:
  f6c8cf87  solo      packed    outdoor+cultural  no diet      Tokyo (Shibuya)
  dc51cbb4  couple    balanced  food+romantic     halal        Williamsburg, Brooklyn
  a678ded5  friends   relaxed   outdoor+scenic    vegetarian   Trastevere, Rome
  fa42710a (Ahmed)  couple    balanced   cultural+food     mediterranean, east asian, american   walk+transit  max 20-40 min travel between stops

Output saved to artifacts/presentation_itineraries.txt
"""

from __future__ import annotations
from supabase import create_client
from ml.pipeline import MLPipeline, PipelineConfig
from ml.utilities.geoapify import fetch_places_for_location

import os
import sys

os.environ.setdefault(
    "SUPABASE_URL", "https://rcrbaorbyhnsilcbkptq.supabase.co")
os.environ.setdefault(
    "SUPABASE_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJjcmJhb3JieWhuc2lsY2JrcHRxIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NjA1Mzg5MSwiZXhwIjoyMDkxNjI5ODkxfQ.Gq_P5S3DQfdIIxPn5wsLsH_KGwGWLULOz0IrGge7Uek",
)
os.environ.setdefault("GEOAPIFY_KEY", "a66b4771072b4953ab9b592125471430")


ARTIFACT = "artifacts/user_profiler.joblib"
RADIUS_M = 2500
LIMIT = 40
START_DATE = "2026-05-01"

# (user_id prefix, location)
DEMO_USERS = ["f6c8cf87", "dc51cbb4", "a678ded5", "fa42710a"]
DEMO_LOCATIONS = ["Shibuya, Tokyo",
                  "Bedford Avenue, Williamsburg, Brooklyn", "Trastevere, Rome"]


def _load_users() -> dict[str, dict]:
    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
    rows = sb.table("preference").select("*").execute().data or []
    result = {}
    for r in rows:
        uid = str(r.get("user_id", ""))
        result[uid] = _normalize(r)
    return result


def _normalize(row: dict) -> dict:
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
        "max_travel_minutes":   row.get("max_travel_minutes", "> 40"),
        "itinerary_pace":       row.get("itinerary_pace", "balanced"),
    }


def _user_summary(u: dict) -> str:
    party = u.get("party_type", "?")
    pace = u.get("itinerary_pace", "?")
    tags = ", ".join((u.get("preferred_tags") or [])[:4])
    diet = ", ".join(u.get("dietary_restrictions") or []) or "none"
    travel = ", ".join(u.get("travel_mode") or [])
    max_t = u.get("max_travel_minutes", "?")
    cuisines = ", ".join((u.get("cuisine_preferences") or [])[:3]) or "any"
    return (
        f"  Party:          {party}\n"
        f"  Pace:           {pace}\n"
        f"  Interests:      {tags}\n"
        f"  Diet:           {diet}\n"
        f"  Cuisines:       {cuisines}\n"
        f"  Gets around by: {travel}\n"
        f"  Max travel:     {max_t} between stops"
    )


def run(out) -> None:
    def p(*args, **kwargs):
        print(*args, **kwargs)
        print(*args, **kwargs, file=out)

    p("Loading users from Supabase …")
    all_users = _load_users()

    p(f"Loading pipeline from {ARTIFACT} …")
    pipeline = MLPipeline.load(PipelineConfig(profiler_path=ARTIFACT))
    pipeline.train_stage2(visits=[], preferences=list(all_users.values()))
    p("Pipeline ready.\n")

    for uid_prefix in DEMO_USERS:
        user = next((u for uid, u in all_users.items()
                    if uid.startswith(uid_prefix)), None)
        if user is None:
            p(f"[!] User {uid_prefix} not found — skipping.")
            continue

        p("=" * 64)
        p(f"  USER  {uid_prefix}…")
        p("=" * 64)
        p(_user_summary(user))
        p()

        for location in DEMO_LOCATIONS:
            p(f"  ── {location} {'─' * (50 - len(location))}")

            try:
                places = fetch_places_for_location(
                    location, radius_m=RADIUS_M, limit=LIMIT)
            except Exception as e:
                p(f"  Could not fetch places: {e}\n")
                continue

            tagged = pipeline.run_stage1(places)
            embedding = pipeline.run_stage2(user)
            ranked = pipeline.run_stage3(
                user_embedding=embedding,
                tagged_places=tagged,
                trip_context=user,
                log_to_db=False,
            )

            if not ranked:
                p("  (no results after filters)\n")
                continue

            trip_context = {**user, "trip_days": 1, "start_date": START_DATE}
            itinerary = pipeline.run_stage4(ranked, trip_context)

            max_t = user.get("max_travel_minutes", "> 40")
            for day in itinerary:
                p(f"  Day {day['day']}  {day.get('date', '')}  [max {max_t} between stops]")
                for stop in day["stops"]:
                    pl = stop["place"]
                    tags = ", ".join(pl.get("tags") or [])
                    travel = stop.get("travel_to_next")
                    leg = (f"  →  {travel['minutes']} min {travel['mode']} "
                           f"({travel['distance_m']}m)") if travel else ""
                    p(f"  {stop['arrival_time']}–{stop['departure_time']}  "
                      f"{pl.get('name', '?'):<38} [{tags}]{leg}")
            p()


def main() -> None:
    out_path = "artifacts/presentation_itineraries.txt"
    with open(out_path, "w", encoding="utf-8") as f:
        run(f)
    print(f"\nSaved to {out_path}")


if __name__ == "__main__":
    main()
