from fastapi import APIRouter, HTTPException, Request

from ml.api.schemas import RecommendRequest, RecommendResponse, ItineraryRequest, ItineraryResponse
from ml.utilities.geoapify import normalize_db_place


def _normalize_places(places: list[dict]) -> list[dict]:
    # Supabase places use lat/lon; Geoapify places use latitude/longitude
    out = []
    for p in places:
        if "lat" in p and "latitude" not in p:
            out.append(normalize_db_place(p))
        else:
            out.append(p)
    return out

router = APIRouter()


@router.post("/recommend", response_model=RecommendResponse)
def recommend(req: RecommendRequest, request: Request):
    pipeline = request.app.state.pipeline

    # convert Pydantic models back to plain dicts so the pipeline TypedDicts accept them
    preference   = req.preference.model_dump()
    places       = _normalize_places([p.model_dump() for p in req.places])
    visits       = [v.model_dump() for v in req.visits] if req.visits else None

    # stage 1 — tag any places that don't already have tags
    tagged = pipeline.run_stage1(places)

    # stage 2 — embed the user (content-only if no visit history is provided)
    embedding = pipeline.run_stage2(preference, visits)

    # stage 3 — score and rank the tagged places
    ranked = pipeline.run_stage3(
        user_embedding=embedding,
        tagged_places=tagged,
        trip_context=preference,
    )

    if not ranked:
        raise HTTPException(status_code=404, detail="No places passed the filters for this preference.")

    return RecommendResponse(places=ranked)


@router.post("/itinerary", response_model=ItineraryResponse)
def itinerary(req: ItineraryRequest, request: Request):
    pipeline   = request.app.state.pipeline
    preference = req.preference.model_dump()
    preference["trip_days"]  = req.trip_days
    preference["start_date"] = req.start_date

    places = _normalize_places([p.model_dump() for p in req.places])
    visits = [v.model_dump() for v in req.visits] if req.visits else None

    tagged    = pipeline.run_stage1(places)
    embedding = pipeline.run_stage2(preference, visits)
    ranked    = pipeline.run_stage3(
        user_embedding=embedding,
        tagged_places=tagged,
        trip_context=preference,
    )

    if not ranked:
        raise HTTPException(status_code=404, detail="No places passed the filters for this preference.")

    return ItineraryResponse(itinerary=pipeline.run_stage4(ranked, preference))
