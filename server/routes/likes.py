"""
    user ratings route to save users rating of places
"""
from fastapi import APIRouter,HTTPException,Depends
from postgrest.exceptions import APIError
from supabase import Client
from server.config.db import get_db_client,get_current_user
from server.models.likes import ratingsInput

RATINGS_TABLE = 'rating'
router = APIRouter(prefix="/ratings",tags=["ratings"])

@router.post("/")
async def post_rating(data:ratingsInput, user = Depends(get_current_user), client:Client = Depends(get_db_client)):
    """
        post a user's rating of a place
    """
    try:
        rating = data.model_dump()
        rating['user_id'] = user.user.id
        response = (
            client.table(RATINGS_TABLE)
            .insert(rating)
            .execute()
        )
        return {"status": "success", "data":response.data}
    except APIError as e:
        raise HTTPException(status_code=400,detail=str(e.message))

@router.get("/")
async def get_rating(user = Depends(get_current_user), client:Client = Depends(get_db_client)):
    """
        get all of user's ratings
    """
    try:
        response = (
            client.table(RATINGS_TABLE)
            .select('*')
            .eq('user_id',user.user.id)
            .execute()
        )
        return {"status": "success", "data":response.data}
    except APIError as e:
        raise HTTPException(status_code=400,detail=str(e.message))

@router.put("/{id}")
async def update_rating(id:str,data:ratingsInput, user = Depends(get_current_user), client:Client = Depends(get_db_client)):
    """
        update a user's rating of a place
    """
    try:
        rating = data.model_dump()
        response = (
            client.table(RATINGS_TABLE)
            .update(rating)
            .eq('id',id)
            .eq('user_id',user.user.id)
            .execute()
        )
        return {"status": "success", "data":response.data}
    except APIError as e:
        raise HTTPException(status_code=400,detail=str(e.message))

@router.delete("/{id}")
async def delete_rating(id:str,user = Depends(get_current_user), client:Client = Depends(get_db_client)):
    """
        delete a user's rating of a place
    """
    try:
        response = (
            client.table(RATINGS_TABLE)
            .delete()
            .eq('id',id)
            .eq('user_id',user.user.id)
            .execute()
        )
        return {"status": "success", "data":response.data}
    except APIError as e:
        raise HTTPException(status_code=400,detail=str(e.message))
