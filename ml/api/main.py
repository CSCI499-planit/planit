"""
    ML service entry point.
    Runs separately from server/main.py on its own port (default 8001).
    The main server calls this over HTTP whenever it needs recommendations.

    Start with: uvicorn ml.api.main:app --port 8001 --reload
"""

import os
import logging
from contextlib import asynccontextmanager

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ml.api.routes.recommend import router as recommend_router
from ml.api.routes.profile   import router as profile_router
from ml.pipeline import MLPipeline

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

ML_PORT = int(os.getenv("ML_PORT", "8001"))
ML_HOST = os.getenv("ML_HOST", "0.0.0.0")


@asynccontextmanager
async def lifespan(app: FastAPI):
    pipeline = MLPipeline()

    try:
        from supabase import create_client
        sb = create_client(os.getenv("SUPABASE_URL", ""), os.getenv("SUPABASE_KEY", ""))

        prefs = sb.table("user_preference").select("*").execute().data or []
        interactions = sb.table("user_interactions").select("*").execute().data or []

        if prefs:
            from ml.models.user_profiler import parse_app_interactions
            visits = parse_app_interactions(interactions, user_id=None) if interactions else []
            pipeline.train_stage2(visits=visits, preferences=prefs)
            logger.info("Pipeline trained on %d preferences, %d interactions.", len(prefs), len(interactions))
        else:
            logger.warning("No preference data in Supabase — running in content-only mode.")

    except Exception as e:
        logger.warning("Startup training failed (%s) — pipeline will use cold-start mode.", e)

    app.state.pipeline = pipeline
    logger.info("ML pipeline ready.")
    yield


app = FastAPI(
    title="PlanIt ML Service",
    description="Recommendation engine for PlanIt — stages 1–3 of the ML pipeline.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten this in production to the main server's URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(recommend_router)
app.include_router(profile_router)


@app.get("/health")
def health():
    # quick check the main server can call to confirm the ML service is up
    pipeline_ready = hasattr(app.state, "pipeline") and app.state.pipeline is not None
    return {"status": "ok", "pipeline_loaded": pipeline_ready}


if __name__ == "__main__":
    uvicorn.run(app, host=ML_HOST, port=ML_PORT)
