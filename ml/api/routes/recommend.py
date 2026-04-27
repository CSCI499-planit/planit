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


def _enrich_visits(visits: list[dict], place_tag_db: dict[str, list[str]]) -> list[dict]:
    return [
        {**v, "tags": v.get("tags") or place_tag_db.get(v.get("place_id", ""), [])}
        for v in visits
    ]


@router.post("/recommend", response_model=RecommendResponse)
def recommend(req: RecommendRequest, request: Request):
    pipeline     = request.app.state.pipeline
    place_tag_db = getattr(request.app.state, "place_tag_db", {})

    preference = req.preference.model_dump()
    places     = _normalize_places([p.model_dump() for p in req.places])
    visits     = _enrich_visits([v.model_dump() for v in req.visits], place_tag_db) if req.visits else None

    tagged    = pipeline.run_stage1(places)
    embedding = pipeline.run_stage2(preference, visits)
    ranked    = pipeline.run_stage3(
        user_embedding=embedding,
        tagged_places=tagged,
        trip_context=preference,
        top_k=req.top_k,
        ensure_itinerary_buffer=False,
        excluded_ids=set(req.excluded_place_ids),
    )

    if not ranked:
        raise HTTPException(status_code=404, detail="No places passed the filters for this preference.")

    return RecommendResponse(places=ranked)


@router.post("/itinerary", response_model=ItineraryResponse)
def itinerary(req: ItineraryRequest, request: Request):
    pipeline     = request.app.state.pipeline
    place_tag_db = getattr(request.app.state, "place_tag_db", {})

    preference = req.preference.model_dump()
    preference["trip_days"]      = req.trip_days
    preference["start_date"]     = req.start_date
    preference["hotel_location"] = req.hotel_location.model_dump() if req.hotel_location else None

    places = _normalize_places([p.model_dump() for p in req.places])
    visits = _enrich_visits([v.model_dump() for v in req.visits], place_tag_db) if req.visits else None

    tagged    = pipeline.run_stage1(places)
    embedding = pipeline.run_stage2(preference, visits)
    ranked    = pipeline.run_stage3(
        user_embedding=embedding,
        tagged_places=tagged,
        trip_context=preference,
        top_k=req.top_k,
        excluded_ids=set(req.excluded_place_ids),
    )

    if not ranked:
        raise HTTPException(status_code=404, detail="No places passed the filters for this preference.")

    return ItineraryResponse(itinerary=pipeline.run_stage4(ranked, preference))
