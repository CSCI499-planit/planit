"""
Generates synthetic interactions for the 27 existing preference-survey users
to bootstrap collaborative filtering past MIN_SVD_USERS=20.

Inspired by the synthetic interaction bootstrapping approach in:
  Javvadhi & Yogi (2025), "Cold Start to Warm Glow: Tackling Sparsity and
  Scalability in Modern Recommender Systems" (Section 4.5 — synthetic dataset construction)
  Full paper can be found at docs/references/javvadhi_yogi_2025_cold_start.pdf

Candidate places: uses place_ids in recommendation_logs.
Decision logic (persona matching):
  - LIKE   → place tagged with a rich signal derived from the user's full
              preference profile: preferred_tags as base, extended with budget,
              exploration score, pace, use_case, dietary, and cuisine signals
  - UNLIKE → place tagged with party-aversion tags

Users grouped by party_type share a pool of liked places (60% overlap) so
SVD can detect within-group correlation. like_tags are further differentiated
per user so the user×tag CF matrix has more signal than party_type alone.

"""

from __future__ import annotations

import logging
import os
import random
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── Configurable ──────────────────────────────────────────────────────────────────
LIKES_PER_USER = 15   # positive interactions per user
UNLIKES_PER_USER = 5  # negative interactions per user
# timestamps spread over this many past days. If too short, retrain may not
# pick up new interactions due to recency bias.
DAYS_SPREAD = 80
RANDOM_SEED = 42
TABLE = "user_interactions"
USER_TABLE = "user"
# fraction of likes drawn from group-shared pool (for CF signal)
SHARED_POOL_PCT = 0.6
# ─────────────────────────────────────────────────────────────────────────────

# Aversion tags by party type, stamped on unlike interactions
_PARTY_AVERSION: dict[str, list[str]] = {
    "solo":    ["family_friendly"],
    "couple":  ["family_friendly", "nightlife"],
    "friends": ["wellness"],
    "family":  ["nightlife", "adventurous"],
    "mixed":   ["nightlife"],
}

# Fallback preferred tags by party type, used only when preferred_tags is empty
_PARTY_PREFERRED: dict[str, list[str]] = {
    "solo":    ["cultural", "scenic", "historical", "quick_visit"],
    "couple":  ["romantic", "upscale", "scenic", "food_and_drink"],
    "friends": ["nightlife", "food_and_drink", "adventurous", "outdoor"],
    "family":  ["family_friendly", "outdoor", "scenic", "budget_friendly"],
    "mixed":   ["outdoor", "food_and_drink", "cultural", "scenic"],
}


def _random_past_dt(days: int) -> str:
    delta = timedelta(days=random.uniform(1, days))
    return (datetime.now(timezone.utc) - delta).isoformat()


def _paginate(sb, table: str, page_size: int = 1000) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    while True:
        batch = (
            sb.table(table)
            .select("*")
            .range(offset, offset + page_size - 1)
            .execute()
            .data or []
        )
        rows.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size
    return rows


def _ensure_stub_users(sb, user_ids: list[str], existing_ids: set[str]) -> None:
    # user_interactions.user_id is a FK to user.id. preference user_ids are
    # random UUIDs that may not exist in the user table yet
    missing = [uid for uid in user_ids if uid not in existing_ids]
    if not missing:
        return
    stubs = [
        {"id": uid, "name": f"sim_{uid[:8]}", "email": f"sim_{uid}@planit.sim"}
        for uid in missing
    ]
    logger.info(
        "Creating %d stub user row(s) for missing FK references…", len(stubs))
    sb.table(USER_TABLE).upsert(stubs, on_conflict="id").execute()


def run(dry_run: bool = False) -> None:
    random.seed(RANDOM_SEED)

    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_KEY", "")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set.")

    sb = create_client(url, key)

    # ── fetch data ────────────────────────────────────────────────────────────
    logger.info("Fetching preferences…")
    prefs = _paginate(sb, "preference")
    logger.info("  %d records", len(prefs))

    logger.info("Fetching candidate place_ids from recommendation_logs…")
    rec_logs = _paginate(sb, "recommendation_logs")
    candidate_place_ids = list({r["place_id"]
                               for r in rec_logs if r.get("place_id")})
    logger.info("  %d unique place_ids available", len(candidate_place_ids))

    if not candidate_place_ids:
        logger.error(
            "No place_ids in recommendation_logs — run at least one recommendation first.")
        return

    logger.info("Fetching existing user rows…")
    existing_users = {str(r["id"]) for r in _paginate(sb, USER_TABLE)}

    logger.info("Fetching existing interactions (duplicate guard)…")
    existing_ints: set[tuple[str, str]] = {
        (str(r["user_id"]), str(r["place_id"])) for r in _paginate(sb, TABLE)
    }
    logger.info("  %d existing interactions", len(existing_ints))

    # ── group place pool by party_type for within-group CF signal ─────────────
    # Sort place_ids so the shared pools are deterministic across runs
    sorted_places = sorted(candidate_place_ids)
    group_pools: dict[str, list[str]] = {}
    for party in _PARTY_PREFERRED:
        shuffled = sorted_places[:]
        random.shuffle(shuffled)
        group_pools[party] = shuffled

    # ── build interaction rows ────────────────────────────────────────────────
    pref_user_ids = [str(p.get("user_id") or "")
                     for p in prefs if p.get("user_id")]
    rows_to_insert: list[dict] = []
    stats: dict[str, int] = {"like": 0, "unlike": 0}

    shared_pool_size = max(1, int(len(candidate_place_ids) * SHARED_POOL_PCT))

    for pref in prefs:
        user_id = str(pref.get("user_id") or "")
        if not user_id:
            continue

        party = (pref.get("party_type") or "mixed").lower()

        # Build like_tags from the user's full preference profile
        pref_tags = list(pref.get("preferred_tags") or []
                         ) or _PARTY_PREFERRED.get(party, ["outdoor"])
        derived: list[str] = []

        budget = pref.get("daily_budget_tier") or 0
        if budget in (1, 2):
            derived.append("budget_friendly")
        elif budget in (3, 4):
            derived.append("upscale")

        if (pref.get("exploration_score") or 0) >= 4:
            derived.append("adventurous")

        pace = (pref.get("itinerary_pace") or "").lower()
        if pace == "relaxed":
            derived += ["scenic", "wellness"]

        use_case = (pref.get("use_case") or "").lower()
        if use_case == "travel":
            derived += ["cultural", "historical"]
        elif use_case == "local":
            derived.append("quick_visit")

        dietary = pref.get("dietary_restrictions") or []
        if any(d in dietary for d in ("halal", "vegetarian", "vegan")):
            derived.append("food_and_drink")

        if pref.get("cuisines_preferences"):
            derived.append("food_and_drink")

        seen: set[str] = set(pref_tags)
        for tag in derived:
            if tag not in seen:
                pref_tags.append(tag)
                seen.add(tag)

        like_tags = pref_tags
        unlike_tags = _PARTY_AVERSION.get(party, ["nightlife"])

        pool = group_pools.get(party, sorted_places)[:]
        # shared prefix (liked by whole group) + personal tail
        shared = pool[:shared_pool_size]
        personal = pool[shared_pool_size:]
        random.shuffle(personal)
        ordered = shared + personal

        likes = 0
        unlikes = 0

        for pid in ordered:
            if likes >= LIKES_PER_USER and unlikes >= UNLIKES_PER_USER:
                break
            if (user_id, pid) in existing_ints:
                continue

            if likes < LIKES_PER_USER:
                rows_to_insert.append({
                    "user_id":    user_id,
                    "place_id":   pid,
                    "event_type": "like",
                    "metadata":   {"tags": like_tags, "simulated": True},
                    "created_at": _random_past_dt(DAYS_SPREAD),
                })
                likes += 1
                stats["like"] += 1
            elif unlikes < UNLIKES_PER_USER:
                rows_to_insert.append({
                    "user_id":    user_id,
                    "place_id":   pid,
                    "event_type": "unlike",
                    "metadata":   {"tags": unlike_tags, "simulated": True},
                    "created_at": _random_past_dt(DAYS_SPREAD),
                })
                unlikes += 1
                stats["unlike"] += 1

    n_users = len({r["user_id"] for r in rows_to_insert})
    logger.info(
        "Planned: %d rows across %d users  (like=%d  unlike=%d)",
        len(rows_to_insert), n_users, stats["like"], stats["unlike"],
    )
    logger.info(
        "CF will activate: %s  (need %d users, have %d)",
        "GOOD TO GO" if n_users >= 20 else "NO, increase LIKES_PER_USER or add more preferences",
        20, n_users,
    )

    if dry_run:
        logger.info("Dry-run — nothing written.")
        return

    if not rows_to_insert:
        logger.info("Nothing to insert.")
        return

    if not dry_run:
        _ensure_stub_users(sb, pref_user_ids, existing_users)

    PAGE = 500
    for i in range(0, len(rows_to_insert), PAGE):
        batch = rows_to_insert[i: i + PAGE]
        sb.table(TABLE).insert(batch).execute()
        logger.info("  inserted rows %d-%d", i + 1, i + len(batch))

    logger.info("Done. %d interactions written.", len(rows_to_insert))
    logger.info("Trigger /admin/retrain on the ML service to apply immediately.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Simulate user interactions.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Plan without writing to DB.")
    args = parser.parse_args()

    run(dry_run=args.dry_run)
