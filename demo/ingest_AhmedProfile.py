"""
Ingest Ahmed's Google Takeout data into Supabase (one-time setup script).
Requires SUPABASE_URL, SUPABASE_KEY, and GEOAPIFY_KEY in the environment (or .env).

Usage: python demo/ingest_AhmedProfile.py --takeout-dir /path/to/takeout [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path

from ml.models.user_profiler import (
    parse_google_takeout,
    parse_google_reviews,
    parse_google_saved_places,
)


MY_PREFERENCE: dict = {
    "use_case":             "mixed",
    "party_type":           "couple",      
    "daily_budget_tier":    2,          
    "trip_budget_tier":     2,
    "preferred_tags":       ["cultural", "food_and_drink", "historical", "scenic"],
    "exploration_score":    4,             
    "popularity_weight":    3,             
    "cuisines_preferences": ["mediterranean", "east asian", "american"],
    "dietary_restrictions": [],           
    "travel_mode":          ["walk", "transit"],
    "max_travel_minutes":   "20-40",       
    "itinerary_pace":       "balanced",
}


def find_files(root: Path, pattern: str) -> list[Path]:
    return sorted(root.rglob(pattern))


def load_timeline(root: Path) -> list[dict]:
    months = []
    for f in find_files(root, "*_*.json"):
        if f.parent.name[:4].isdigit():
            try:
                months.append(json.loads(f.read_text(encoding="utf-8")))
            except Exception:
                pass
    return months


def load_json_if_exists(paths: list[Path]) -> dict | None:
    for p in paths:
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                pass
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--takeout-dir", required=True, type=Path,
                        help="Path to the root of your extracted Google Takeout folder")
    parser.add_argument("--user-id", default=None,
                        help="User ID to assign (default: auto-generated UUID)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print summary without writing to Supabase")
    args = parser.parse_args()

    root    = args.takeout_dir.expanduser().resolve()
    AHMED_UUID = "fa42710a-6aec-48ec-840f-909ee2157864"
    user_id = args.user_id if args.user_id and len(args.user_id) == 36 and args.user_id.count("-") == 4 \
              else AHMED_UUID

    if not root.exists():
        print(f"[!] Directory not found: {root}")
        sys.exit(1)

    print(f"\nScanning {root} …\n")

    # Timeline visits
    timeline_months = load_timeline(root)
    timeline_visits = []
    if timeline_months:
        timeline_visits = parse_google_takeout(timeline_months, user_id, place_tag_db={})
        print(f"  Timeline  : {len(timeline_months)} month files, {len(timeline_visits)} unique places")
    else:
        print("Nothing found")

    # Reviews
    reviews_data   = load_json_if_exists([
        root / "Reviews.json",
        root / "Maps (your places)" / "Reviews.json",
        root / "Maps" / "Reviews.json",
    ])
    review_visits  = []
    if reviews_data:
        review_visits = parse_google_reviews(reviews_data, user_id)
        print(f"  Reviews   : {len(review_visits)} places")
    else:
        print("  Reviews   : Reviews.json not found")

    # Saved places
    saved_data    = load_json_if_exists([
        root / "Saved Places.json",
        root / "Saved places.json",
        root / "Maps (your places)" / "Saved Places.json",
        root / "Maps (your places)" / "Saved places.json",
        root / "Maps" / "Saved Places.json",
        root / "Maps" / "Saved places.json",
    ])
    saved_visits  = []
    if saved_data:
        saved_visits = parse_google_saved_places(saved_data, user_id)
        print(f"  Saved     : {len(saved_visits)} places")
    else:
        print("  Saved     : Saved places.json not found")

    all_visits = timeline_visits + review_visits + saved_visits
    print(f"\n  Total visits across all sources: {len(all_visits)}")

    # Tag summary
    from collections import Counter
    tag_counts: Counter = Counter()
    for v in all_visits:
        tag_counts.update(v.get("tags") or [])

    if tag_counts:
        print("\n  Top inferred interests:")
        for tag, count in tag_counts.most_common(8):
            print(f"    {tag:<20} {count}")

    pref_row = {"user_id": user_id, **MY_PREFERENCE}
    print(f"\n  Preference profile (user_id={user_id}):")
    for k, v in pref_row.items():
        print(f"    {k:<25} {v}")

    if args.dry_run:
        print("\n[dry-run] Nothing written to Supabase.")
        return

    from supabase import create_client
    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

    print("\nWriting to Supabase …")

    # upsert preference row
    sb.table("preference").upsert(pref_row).execute()
    print(f"  preference row upserted (user_id={user_id})")


    if all_visits:
        interaction_rows = []
        for v in all_visits:
            pid    = v.get("place_id", "")
            rating = float(v.get("rating") or 3.0)
            if not pid:
                continue
            if rating >= 5.0:
                event = "itinerary_like"
            elif rating >= 4.0:
                event = "like"
            elif rating < 2.0:
                event = "unlike"
            else:
                continue  # neutral — skip
            interaction_rows.append({
                "user_id":    v.get("user_id", user_id),
                "place_id":   pid,
                "event_type": event,
                "metadata":   {"tags": v.get("tags") or [], "source": "google_takeout"},
            })

        for i in range(0, len(interaction_rows), 100):
            sb.table("user_interactions").upsert(interaction_rows[i : i + 100]).execute()
        print(f"{len(interaction_rows)} interaction rows upserted ({len(all_visits) - len(interaction_rows)} neutral skipped)")

if __name__ == "__main__":
    main()
