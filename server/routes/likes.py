"""
    user ratings route for users to rate places
"""
from fastapi import APIRouter,Depends,HTTPException
from postgrest.exceptions import APIError
from datetime import datetime
from uuid import uuid4
from server.config.db import get_db_client,get_current_user
from server.models.likes import ratingsInput

RATINGS_TABLE = 'user_ratings'
router = APIRouter(prefix="/ratings",tags=["ratings"])

@router.post("/")
async def post_rating(data:ratingsInput, user = Depends(get_current_user), client = Depends(get_db_client)):
    """
        post user ratings
    """
    try:
        rating = data.model_dump()
        rating['id'] = uuid4()
        rating['user_id'] = user.user.id
        rating['created_at'] = datetime.now()
        response = (
            client.table(RATINGS_TABLE)
            .insert(rating)
            .execute()
        )
        return {"status": "success", "data":response.data}
    except APIError as e:
        raise HTTPException(status_code=400,detail=str(e.message))

@router.get("/")
async def get_rating(user = Depends(get_current_user), client = Depends(get_db_client)):
    """
        get user ratings
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

@router.put("/")
async def update_rating(data:ratingsInput, user = Depends(get_current_user), client = Depends(get_db_client)):
    """
        update user rating
    """
    try:
        rating = data.model_dump()
        response = (
            client.table(RATINGS_TABLE)
            .update(rating)
            .eq('user_id',user.user.id)
            .execute()
        )
        return {"status": "success", "data":response.data}
    except APIError as e:
        raise HTTPException(status_code=400,detail=str(e.message))

@router.delete("/{id}")
async def delete_rating(id,user = Depends(get_current_user), client = Depends(get_db_client)):
    """
        delete user ratings
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
