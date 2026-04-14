"""
    user account route to store account details
"""
from fastapi import APIRouter, Depends,HTTPException
from postgrest.exceptions import APIError
import bcrypt
from datetime import datetime
from uuid import uuid4
from server.config.db import get_db_client,get_current_user
from server.models.users import userInput

USER_TABLE = 'users'
router = APIRouter(prefix="/users",tags=["users"])

def user_exist(id, client =  Depends(get_db_client)):
    user = client.table(USER_TABLE).select('*').eq('id',id).execute()
    return len(user.data) > 0

@router.post("/")
async def create_user(data:userInput, user = Depends(get_current_user), client = Depends(get_db_client)):
    """
        create user
    """
    try:
        if user_exist(user.user.id):
            return {'message': 'user already exist'}
        user_data = data.model_dump()
        user_data['id'] = uuid4()
        user_data['password'] = bcrypt.hashpw(user_data['password'], bcrypt.gensalt())
        user_data['created_at'] = datetime.now()
        response = (
            client.table(USER_TABLE)
            .insert(user_data)
            .execute()
        )
        return {"status":"success",'message': 'user created',"data":response.data}
    except APIError as e:
        raise HTTPException(status_code=400,detail=str(e.message))
    
@router.get("/")
async def get_user(user = Depends(get_current_user), client = Depends(get_db_client)):
    """
        get user data
    """
    try:
        response = (
            client.table(USER_TABLE)
            .select('*')
            .eq('id', user.user.id)
            .execute()
        )
        return {"status":"success", "data": response.data}
    except APIError as e:
        raise HTTPException(status_code=400,detail=str(e.message))

@router.put("/")
async def update_user(data:userInput, user = Depends(get_current_user), client = Depends(get_db_client)):
    """
        update user data
    """
    try:
        if user_exist(user.user.id, client):
            user_data = data.model_dump()
            response = (
                client.table(USER_TABLE)
                .update(user_data)
                .eq('id', user.user.id)
                .execute()
            )
        return {"message": 'user updated', "data":response.data}
    except APIError as e:
        raise HTTPException(status_code=400,detail=str(e.message))

@router.delete("/")
async def delete_user(user = Depends(get_current_user), client = Depends(get_db_client)):
    """
        delete user data
    """
    try:
        if user_exist(user.user.id):
            response = (
                client.table(USER_TABLE)
                .delete()
                .eq('id', user.user.id)
                .execute()
            )
        return {'message': 'user deleted', "data":response.data}
    except APIError as e:
        raise HTTPException(status_code=400,detail=str(e.message))
