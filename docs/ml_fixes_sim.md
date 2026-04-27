# ML Bug Fixes & Interaction Simulation

_2026-04-26_

---

## Critical Fix: CF Cold Start

`place` table is always empty. Places come from Geoapify per-request and were never persisted. `place_tag_db` was always `{}` at retrain time, every interaction had `tags=[]`, CF matrix stayed at 0 rows.

**Fix:** `place_tag_db` moved into `UserProfiler` and included in the joblib artifact. `run_stage1` now writes `{place_id: tags}` on every recommendation call so the cache builds naturally. `_fetch_and_train` seeds from that cache instead of the empty table. `app.state.place_tag_db` is a live reference to the same dict so recommendation updates are instant.

---

## Interaction Feedback Loop

- `POST/GET /interactions` added, logs likes, unlikes, itinerary likes/dislikes
- Visit history now forwarded to ML on every recommendation call
- Disliked places excluded via `excluded_place_ids` through the full chain: server -> schemas -> pipeline -> recommender
- Impression negatives: top-5 shown with no positive interaction gets rating 2.0 at retrain
- Recency weighting: 60-day half-life exponential decay on all interactions

---

## User Interactions Simulation

Added `ml/data/simulate_interactions.py` which simulates user interactions for the 27 surveys that was collected which helps us get past the `MIN_SVD_USERS=20` wall to enable the CF.

---

## Route Optimizer

- Hotel coords used as VRPTW depot instead of centroid of candidates
- Opening hours enforced in time windows
- `AddDisjunction` lets solver drop weak stops
- `_dwell_minutes` now takes max across matching tags, not first match

---

## Other Fixes

- Nullable `popularity_weight` / `daily_budget_tier` crashes fixed in recommender
- `EVENT_RATINGS` moved to ML package
- `top_k` now dynamic in `run_stage3`: `max(rec_top_k, max_per_day * trip_days + 10)`
- Score fields renamed from `_cf_score` to `score_breakdown`
- OSM match radius increased: 80m -> 150m

---

## Deployment Prepration

- Artifact stored in Supabase Storage (`ml-artifacts`)
- `render.yaml` added for both services
- `httpx` added as explicit dep
