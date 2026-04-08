"""
    user preference route to store user preferences
"""
from fastapi import APIRouter, Depends,HTTPException
from postgrest.exceptions import APIError
from datetime import datetime
from uuid import uuid4
from server.config.db import get_db_client, get_current_user
from server.models.preferences import preferenceInput

PREFERENCE_TABLE = 'user_preference'
router = APIRouter(prefix="/preference",tags=["preference"])

@router.post("/")
async def post_preference(data:preferenceInput, user = Depends(get_current_user), client = Depends(get_db_client)):
    """
        post user preference data
    """
    try:
        preference = data.model_dump()
        preference['id'] = uuid4()
        preference['user_id'] = user.user.id
        preference['created_at'] = datetime.now()
        response = (
            client.table(PREFERENCE_TABLE)
            .insert(preference)
            .execute()
        )
        return {"status": "success", "data":response.data}
    except APIError as e:
        raise HTTPException(status_code=400,detail=str(e.message))

@router.get("/")
async def get_preference(client = Depends(get_db_client), user=Depends(get_current_user)):
    """
        get user's preference form
    """
    try:
        response = (
            client.table(PREFERENCE_TABLE)
            .select('*')
            .eq('user_id',user.user.id)
            .execute()
        )
        return {"status": "success", "data":response.data}
    except APIError as e:
        raise HTTPException(status_code=400,detail=str(e.message))
    
@router.put("/")
async def update_preference(data:preferenceInput, client = Depends(get_db_client), user=Depends(get_current_user)):
    """
        update user's preference
    """
    try:
        preference = data.model_dump()
        response = (
            client.table(PREFERENCE_TABLE)
            .update(preference)
            .eq('user_id',user.user.id)
            .execute()
        )
        return {"status": "success", "data":response.data}
    except APIError as e:
        raise HTTPException(status_code=400,detail=str(e.message))

@router.delete("/")
async def delete_preference(client = Depends(get_db_client), user=Depends(get_current_user)):
    """
        delete user's preference data
    """
    try:
        response = (
            client.table(PREFERENCE_TABLE)
            .delete()
            .eq('user_id',user.user.id)
            .execute()
        )
        return {"status": "success", "data":response.data}
    except APIError as e:
        raise HTTPException(status_code=400,detail=str(e.message))
