"""
ML pipeline benchmark — tests the real user flow end-to-end.

A user fills out a survey. The ML service reads that survey and gives them
place recommendations or a full itinerary. This script verifies that flow
works correctly across different user profiles.

Run from project root:
    python -m ml.benchmark
"""

from __future__ import annotations

import sys
import numpy as np

from ml.models.recommender import HybridRecommender
from ml.models.user_profiler import UserProfiler, EMBEDDING_DIM
from ml.pipeline import MLPipeline

PASS = "\033[92m PASS\033[0m"
FAIL = "\033[91m FAIL\033[0m"

results: list[tuple[str, bool, str]] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    results.append((name, condition, detail))
    status = PASS if condition else FAIL
    print(f"{status}  {name}" + (f"  ({detail})" if detail else ""))


# ---------------------------------------------------------------------------
# Test places — what the frontend would pass in from Geoapify/Supabase
# ---------------------------------------------------------------------------

PLACES = [
    {
        "place_id": "p1", "name": "Riverside Park",
        "latitude": 40.80, "longitude": -73.96,
        "categories": ["leisure.park", "natural.beach"],
        "price_level": None, "rating": 4.2, "review_count": 800,
        "hours": None, "attributes": None, "tags": None,
    },
    {
        "place_id": "p2", "name": "Corner Cafe",
        "latitude": 40.73, "longitude": -73.99,
        "categories": ["catering.cafe", "catering.restaurant"],
        "price_level": 2, "rating": 4.5, "review_count": 300,
        "hours": None, "attributes": {"cuisine": "italian"}, "tags": None,
    },
    {
        "place_id": "p3", "name": "City Museum",
        "latitude": 40.76, "longitude": -73.98,
        "categories": ["entertainment.museum", "tourism.sights"],
        "price_level": 3, "rating": 4.8, "review_count": 5000,
        "hours": None, "attributes": None, "tags": None,
    },
    {
        "place_id": "p4", "name": "Grand Hotel Bar",
        "latitude": 40.75, "longitude": -73.97,
        "categories": ["catering.bar", "accommodation.hotel"],
        "price_level": 4, "rating": 4.9, "review_count": 2000,
        "hours": None, "attributes": None, "tags": None,
    },
    {
        "place_id": "p5", "name": "Rooftop Garden",
        "latitude": 40.74, "longitude": -73.98,
        "categories": ["leisure.garden"],
        "price_level": 3, "rating": 4.6, "review_count": 400,
        "hours": None, "attributes": {"Romantic": "true"}, "tags": None,
    },
    {
        "place_id": "p6", "name": "Local Gym",
        "latitude": 40.77, "longitude": -73.95,
        "categories": ["sport.fitness"],
        "price_level": 2, "rating": 4.0, "review_count": 150,
        "hours": None, "attributes": None, "tags": None,
    },
]

# ---------------------------------------------------------------------------
# User survey profiles — what the onboarding form produces
# ---------------------------------------------------------------------------

# User A — outdoor explorer, solo trip, budget-conscious
USER_A = {
    "user_id": "user-a",
    "use_case": "travel",
    "party_type": "solo",
    "daily_budget_tier": 2,
    "trip_budget_tier": 2,
    "preferred_tags": ["outdoor", "adventurous", "scenic"],
    "exploration_score": 5,
    "popularity_weight": 2,
    "cuisine_preferences": ["american"],
    "dietary_restrictions": [],
    "travel_mode": ["walk"],
    "max_travel_minutes": "20-40",
    "itinerary_pace": "packed",
}

# User B — couple, romantic, fine dining, upscale
USER_B = {
    "user_id": "user-b",
    "use_case": "daytrip",
    "party_type": "couple",
    "daily_budget_tier": 4,
    "trip_budget_tier": 4,
    "preferred_tags": ["romantic", "upscale", "food_and_drink"],
    "exploration_score": 2,
    "popularity_weight": 5,
    "cuisine_preferences": ["italian", "mediterranean"],
    "dietary_restrictions": [],
    "travel_mode": ["drive"],
    "max_travel_minutes": "20-40",
    "itinerary_pace": "relaxed",
}

# User C — family trip, budget-friendly, kid-friendly
USER_C = {
    "user_id": "user-c",
    "use_case": "travel",
    "party_type": "family",
    "daily_budget_tier": 1,
    "trip_budget_tier": 2,
    "preferred_tags": ["family_friendly", "outdoor", "budget_friendly"],
    "exploration_score": 3,
    "popularity_weight": 4,
    "cuisine_preferences": ["american"],
    "dietary_restrictions": [],
    "travel_mode": ["drive"],
    "max_travel_minutes": "> 40",
    "itinerary_pace": "balanced",
}

pipeline  = MLPipeline()
profiler  = UserProfiler()
rec       = HybridRecommender()
tagged    = pipeline.run_stage1(PLACES)

# ---------------------------------------------------------------------------
# 1. Survey → embedding (content-only, no interaction history)
# ---------------------------------------------------------------------------
print("\n── 1. Survey → Embedding ──")
print("   (content-only mode — no interaction history needed)")

emb_a = profiler.embed_user(USER_A)
emb_b = profiler.embed_user(USER_B)
emb_c = profiler.embed_user(USER_C)

check("User A embedding is 48-dim",   emb_a.shape == (EMBEDDING_DIM,), f"shape={emb_a.shape}")
check("User B embedding is 48-dim",   emb_b.shape == (EMBEDDING_DIM,), f"shape={emb_b.shape}")
check("User A embedding is unit norm", bool(abs(np.linalg.norm(emb_a) - 1.0) < 1e-5))
check("User B embedding is unit norm", bool(abs(np.linalg.norm(emb_b) - 1.0) < 1e-5))
check("User A and B embeddings differ",
      bool(not np.allclose(emb_a, emb_b)),
      f"cosine_sim={float(np.dot(emb_a, emb_b)):.3f}")
check("User A and C embeddings differ",
      bool(not np.allclose(emb_a, emb_c)),
      f"cosine_sim={float(np.dot(emb_a, emb_c)):.3f}")

# ---------------------------------------------------------------------------
# 2. Survey → recommendations (the core use case)
# ---------------------------------------------------------------------------
print("\n── 2. Survey → Recommendations ──")

ranked_a = rec.recommend(emb_a, tagged, USER_A)
ranked_b = rec.recommend(emb_b, tagged, USER_B)
ranked_c = rec.recommend(emb_c, tagged, USER_C)

ids_a = [p["place_id"] for p in ranked_a]
ids_b = [p["place_id"] for p in ranked_b]
ids_c = [p["place_id"] for p in ranked_c]

# User A (outdoor, solo) — park should rank above museum (or museum filtered by budget)
_park_rank   = ids_a.index("p1") if "p1" in ids_a else None
_museum_rank = ids_a.index("p3") if "p3" in ids_a else None
_park_above_museum = (
    _park_rank is not None and
    (_museum_rank is None or _park_rank < _museum_rank)
)
check("User A (outdoor): park ranked above museum (or museum budget-filtered)",
      _park_above_museum,
      f"park={_park_rank}  museum={_museum_rank if _museum_rank is not None else 'filtered'}")

# User B (romantic, couple) — rooftop garden should rank highly
check("User B (romantic couple): rooftop garden in top 3",
      "p5" in ids_b and ids_b.index("p5") < 3,
      f"rooftop rank={ids_b.index('p5') if 'p5' in ids_b else 'N/A'}")

# User B (upscale) — luxury bar should appear (price_level=4 matches budget_tier=4)
check("User B (upscale): luxury bar not filtered out",
      "p4" in ids_b,
      f"luxury in results: {'p4' in ids_b}")

# User C (family, budget) — luxury bar (price_level=4) filtered for budget_tier=1
check("User C (budget family): luxury bar filtered out",
      "p4" not in ids_c,
      f"luxury in results: {'p4' in ids_c}")

# Scores are descending for all users
check("User A scores are descending",
      all(ranked_a[i].get("score", 0) >= ranked_a[i+1].get("score", 0) for i in range(len(ranked_a)-1)))
check("User B scores are descending",
      all(ranked_b[i].get("score", 0) >= ranked_b[i+1].get("score", 0) for i in range(len(ranked_b)-1)))

# Score breakdown is present
check("Score breakdown present in results",
      all("_tag_score" in p and "_cf_score" in p for p in ranked_a))

# All scores in valid range
check("All scores between 0 and 1",
      all(0.0 <= p.get("score", 0) <= 1.0 for p in ranked_a + ranked_b + ranked_c))

# ---------------------------------------------------------------------------
# 3. Different users get different recommendations
# ---------------------------------------------------------------------------
print("\n── 3. Personalisation — Different Users, Different Results ──")

check("User A and B get different top result",
      len(ids_a) > 0 and len(ids_b) > 0 and ids_a[0] != ids_b[0],
      f"A top={ids_a[0] if ids_a else 'N/A'}  B top={ids_b[0] if ids_b else 'N/A'}")

overlap_ab = len(set(ids_a[:3]) & set(ids_b[:3]))
check("User A and B top-3 are mostly different",
      overlap_ab <= 1,
      f"overlap in top-3={overlap_ab}")

# ---------------------------------------------------------------------------
# 4. Tag matching drives the score in content-only mode
# ---------------------------------------------------------------------------
print("\n── 4. Tag Matching (primary signal in content-only mode) ──")

top_a = ranked_a[0]
check("Top result for User A has at least one preferred tag",
      any(t in (top_a.get("tags") or []) for t in USER_A["preferred_tags"]),
      f"top place tags={top_a.get('tags')}  preferred={USER_A['preferred_tags']}")

top_b = ranked_b[0]
check("Top result for User B has at least one preferred tag",
      any(t in (top_b.get("tags") or []) for t in USER_B["preferred_tags"]),
      f"top place tags={top_b.get('tags')}  preferred={USER_B['preferred_tags']}")

# ---------------------------------------------------------------------------
# 5. Survey → Itinerary (full pipeline stages 1-4)
# ---------------------------------------------------------------------------
print("\n── 5. Survey → Itinerary ──")

itinerary_a = pipeline.run_stage4(
    ranked_a,
    {**USER_A, "trip_days": 1, "start_date": "2026-04-14"},
)
itinerary_b = pipeline.run_stage4(
    ranked_b,
    {**USER_B, "trip_days": 1, "start_date": "2026-04-14"},
)

check("User A itinerary has 1 day",    len(itinerary_a) == 1)
check("User B itinerary has 1 day",    len(itinerary_b) == 1)

day_a = itinerary_a[0]
day_b = itinerary_b[0]

check("User A itinerary has stops",    len(day_a["stops"]) > 0, f"{len(day_a['stops'])} stops")
check("User B itinerary has stops",    len(day_b["stops"]) > 0, f"{len(day_b['stops'])} stops")

# packed pace (User A) should have more stops than relaxed pace (User B)
check("Packed pace has more stops than relaxed pace",
      len(day_a["stops"]) >= len(day_b["stops"]),
      f"packed={len(day_a['stops'])}  relaxed={len(day_b['stops'])}")

# arrival times chronological
times_a = [int(s["arrival_time"].replace(":", "")) for s in day_a["stops"]]
check("User A arrival times are chronological", times_a == sorted(times_a), f"times={times_a}")

# last stop has no travel leg
check("Last stop has no travel_to_next", day_a["stops"][-1]["travel_to_next"] is None)

# ---------------------------------------------------------------------------
# 6. Cold start — user with minimal survey data still gets results
# ---------------------------------------------------------------------------
print("\n── 6. Cold Start — Minimal Survey ──")

minimal_user = {
    "user_id": "new-user",
    "preferred_tags": ["outdoor"],
    "party_type": "solo",
    "daily_budget_tier": 2,
}
emb_minimal = profiler.embed_user(minimal_user)
ranked_minimal = rec.recommend(emb_minimal, tagged, minimal_user)

check("Minimal survey still produces recommendations", len(ranked_minimal) > 0,
      f"{len(ranked_minimal)} results")
check("Minimal survey embedding is valid",
      bool(emb_minimal.shape == (EMBEDDING_DIM,) and not np.all(emb_minimal == 0)))

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print("\n── Summary ──")
passed = sum(1 for _, ok, _ in results if ok)
failed = sum(1 for _, ok, _ in results if not ok)
total  = len(results)
print(f"  {passed}/{total} passed  |  {failed} failed")

if failed:
    print("\nFailed tests:")
    for name, ok, detail in results:
        if not ok:
            print(f"  ✗ {name}" + (f"  ({detail})" if detail else ""))
    sys.exit(1)
else:
    print("\n  All tests passed.")
