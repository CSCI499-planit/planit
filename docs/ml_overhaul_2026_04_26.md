# ML Pipeline Overhaul — 2026-04-26

## Core Bug Fix: place_tag_db Always Empty

**Problem**
The `place` table in Supabase is always empty. Places come from Geoapify per-request and are never written to the database. `_fetch_and_train` was building `place_tag_db` from that empty table, so every visit in `user_interactions` had `tags=[]` at retrain time. `_build_interaction_matrix` filters for visits with non-empty tags, so the CF user×tag matrix was always 0 rows — SVD never trained, CF weight stayed 0.0 forever.

**Fix**
- `place_tag_db` moved into `UserProfiler` as a dataclass field — it's now included in `joblib.dump` and survives Render restarts via Supabase Storage
- `run_stage1` writes `{place_id: tags}` into `user_profiler.place_tag_db` on every recommendation call — the cache grows organically without any DB writes
- `_fetch_and_train` seeds `place_tag_db` from the accumulated inference cache first, then layers the (empty) place table on top
- `app.state.place_tag_db` is now a live reference to the same dict object — updates from `run_stage1` are immediately visible to `_enrich_visits` without any extra wiring
- `UserProfiler.load()` has a backward-compat guard: old artifacts without the field get `place_tag_db = {}` on load
- `MLPipeline.place_tag_db` is a property that delegates to `user_profiler.place_tag_db`

---

## Interaction Feedback Loop

**Like/Dislike Endpoints**
- Added `server/routes/interactions.py` with `POST /interactions` (log event) and `GET /interactions` (fetch history)
- Valid event types: `like`, `unlike`, `itinerary_like`, `itinerary_dislike`
- Wired into `server/main.py`

**Visit History Forwarded to ML Service**
- `server/routes/recommend.py` now calls `_fetch_user_history(user_id)` before proxying to the ML service
- Fetches `user_interactions` and `rating` rows, aggregates per place, and forwards as `visits` in the request body
- Without this, `embed_user()` ran content-only on every request even for users with rich history

**Disliked Places Excluded**
- `excluded_place_ids` added to `RecommendRequest` and `ItineraryRequest` schemas
- Server extracts place_ids with `unlike` or `itinerary_dislike` events and passes them through
- `HybridRecommender.recommend()` skips any place in `excluded_ids` before scoring
- Prevents disliked places from reappearing in subsequent recommendations

**Impression Negatives**
- `_impression_visits()` added to `ml/api/main.py`
- Places shown in top-5 ranking positions but never positively interacted with → implicit rating 2.0
- Fed back into `tagged_visits` at retrain time
- Only top-5 positions counted (lower ranks may not have been visible in the UI)

**Recency Weighting**
- `_recency_weight(created_at, half_life_days=60)` added to `UserProfiler`
- Exponential decay: `exp(-ln(2) * days_since / 60)` — a 60-day-old interaction is worth half a fresh one
- Applied in `_build_interaction_matrix` when computing cell scores
- `created_at` propagated through `UserVisit`, `UserVisitSchema`, `_ratings_to_visits`, `parse_app_interactions`, and `_fetch_user_history`

**Simulated Interactions for CF Bootstrap**
- `ml/data/simulate_interactions.py` — one-time script to push past `MIN_SVD_USERS=20`
- Uses 100 place_ids from `recommendation_logs` as candidate pool
- 29 existing preference users get 15 likes + 5 unlikes each (580 total rows)
- Tags stored in `metadata: {"tags": [...], "simulated": true}` so `parse_app_interactions` can use them even before `place_tag_db` is populated
- Users grouped by `party_type` with 60% shared pool to create within-group CF correlation
- Creates stub rows in `user` table for preference user_ids that don't have auth accounts (FK requirement)
- `parse_app_interactions` updated to fall back to `row["metadata"]["tags"]` when `place_tag_db` has no entry

---

## Route Optimizer Improvements

- Hotel location passed as VRPTW depot — routes now start from the actual hotel instead of the centroid of candidates
- Opening hours enforced in OR-Tools time windows: `latest_arrival = close - dwell`
- `AddDisjunction` penalties allow the solver to drop weak stops rather than forcing every candidate
- `_build_greedy_day()` fallback also respects time windows via `_filter_open_during_day()`
- `_dwell_minutes()` now takes the max across all matching tags instead of first match

---

## Production Setup

**Supabase Storage for Artifact Persistence**
- Free-tier Render has no persistent disk — artifact is stored in Supabase Storage bucket `ml-artifacts`
- `_download_artifact()` runs at startup if local path doesn't exist
- `_upload_artifact()` runs after every successful retrain
- `ARTIFACT_BUCKET` env var on `planit-ml` Render service (value: `ml-artifacts`)

**Automated Retraining**
- Supabase database trigger on `user_interactions INSERT` calls `POST /webhook/interactions` on the ML service
- Two-gate debounce: `pending_interactions >= RETRAIN_THRESHOLD` (default 10) AND `MIN_RETRAIN_INTERVAL_HOURS` elapsed (default 1h)
- Retrain runs as FastAPI `BackgroundTask` — webhook returns immediately, Supabase 5s timeout is never hit
- `/admin/retrain` for manual hot-swap

**Render Deployment**
- `render.yaml` added with both services: `planit-backend` and `planit-ml`
- `ML_SERVICE_URL` on backend wired from `planit-ml` host property

---

## Other Fixes

- `popularity_weight` and `daily_budget_tier` `None` crashes fixed in `recommender.py` (DB columns are nullable)
- OSM match radius increased 80m → 150m for larger venues (parks, museums)
- `httpx` added as explicit dependency in `pyproject.toml` and `requirements.txt`
- `EVENT_RATINGS` moved to `ml/models/user_profiler.py` as single source of truth — server imports from ML package to avoid circular Supabase client init at import time
- Pydantic score fields renamed: `_cf_score` → `score_breakdown` dict (leading underscore fields are dropped by Pydantic)
- `run_stage3` `top_k` now dynamic: `max(config.rec_top_k, max_per_day * trip_days + 10)` — prevents candidate starvation on long trips
