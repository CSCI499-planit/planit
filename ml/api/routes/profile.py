import numpy as np
from fastapi import APIRouter, HTTPException, Request

from ml.api.schemas import (
    EmbedRequest, EmbedResponse,
    SimilarUsersRequest, SimilarUsersResponse,
)

router = APIRouter()


@router.post("/profile/embed", response_model=EmbedResponse)
def embed_user(req: EmbedRequest, request: Request):
    pipeline   = request.app.state.pipeline
    preference = req.preference.model_dump()
    visits     = [v.model_dump() for v in req.visits] if req.visits else None

    embedding = pipeline.run_stage2(preference, visits)

    return EmbedResponse(
        user_id=req.preference.user_id,
        embedding=embedding.tolist(),
    )


@router.post("/profile/similar", response_model=SimilarUsersResponse)
def similar_users(req: SimilarUsersRequest, request: Request):
    pipeline  = request.app.state.pipeline
    embedding = np.array(req.embedding, dtype=np.float32)

    try:
        similar = pipeline.find_similar_users(embedding, top_k=req.top_k)
    except RuntimeError:
        raise HTTPException(status_code=503, detail="Profiler not fitted yet — try again after retrain.")

    return SimilarUsersResponse(
        users=[{"user_id": uid, "similarity": round(sim, 4)} for uid, sim in similar]
    )
