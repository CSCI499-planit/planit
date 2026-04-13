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
    # load the pipeline once at startup — keeps the joblib model in memory
    # instead of reloading it on every request
    logger.info("Loading ML pipeline...")
    app.state.pipeline = MLPipeline.load()
    logger.info("ML pipeline ready.")
    yield
    # nothing to clean up, but this is where you'd flush caches etc.


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
