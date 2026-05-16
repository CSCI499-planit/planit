from fastapi import APIRouter, HTTPException, Query
from ml.utilities.geoapify import fetch_places_for_location

router = APIRouter()


@router.get("/places/search")
def search_places(
    location:  str = Query(
        ...,
        min_length=2,
        max_length=120,
        description="Neighbourhood, hotel, landmark, or city e.g. 'Trastevere, Rome'",
    ),
    radius_m:  int = Query(5000, ge=100, le=50_000, description="Search radius in metres"),
    limit:     int = Query(50, ge=1, le=100, description="Max number of places to return"),
):
    try:
        places = fetch_places_for_location(
            location, radius_m=radius_m, limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Geoapify error: {e}")

    if not places:
        raise HTTPException(
            status_code=404, detail=f"No places found for {location!r}")

    return {"location": location, "count": len(places), "places": places}
