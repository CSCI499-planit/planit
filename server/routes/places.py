"""
    places route for users to save places
"""
from fastapi import APIRouter,Depends,HTTPException
from postgrest.exceptions import APIError
from server.config.db import get_db_client
from server.models.places import placeInput

PLACE_TABLE = 'places'
router = APIRouter(prefix="/places", tags=["places"])

@router.post("/")
async def create_place(data:placeInput, client = Depends(get_db_client)):
    """
        add place details
    """
    try:
        place = data.model_dump()
        response = (
            client.table(PLACE_TABLE)
            .insert(place)
            .execute()
        )
        return {"status": "success", "data":response.data}
    except APIError as e:
        raise HTTPException(status_code=400,detail=str(e.message))

@router.get("/{id}")
async def get_place(id, client = Depends(get_db_client)):
    """
        get place details
    """
    try:
        response = (
            client.table(PLACE_TABLE)
            .select("*")
            .eq("id",id)
            .execute()
        )
        return {"status": "success", "data":response.data}
    except APIError as e:
        raise HTTPException(status_code=400,detail=str(e.message))

@router.put("/{id}")
async def update_place(id, data:placeInput,client = Depends(get_db_client)):
    """
        update place details
    """
    try:
        place = data.model_dump()
        response = (
            client.table(PLACE_TABLE)
            .update(place)
            .eq("id",id)
            .execute()
        )
        return {"status": "success", "data":response.data}
    except APIError as e:
        raise HTTPException(status_code=400,detail=str(e.message))

@router.delete("/{id}")
async def delete_place(id, client = Depends(get_db_client)):
    """
        delete place details
    """
    try:
        response = (
            client.table(PLACE_TABLE)
            .delete()
            .eq("id",id)
            .execute()
        )
        return {"status": "success", "data":response.data}
    except APIError as e:
        raise HTTPException(status_code=400,detail=str(e.message))
