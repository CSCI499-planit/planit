"""
    user route to store user account details
"""
from fastapi import APIRouter,HTTPException,Depends
from postgrest.exceptions import APIError
from supabase import Client
from server.config.db import get_db_client,get_current_user
from server.models.users import userInput

USER_TABLE = 'user'
router = APIRouter(prefix='/user',tags=['user'])

def user_exist(id:str, client:Client =  Depends(get_db_client)):
    user = client.table(USER_TABLE).select('*').eq('id',id).execute()
    return len(user.data) > 0

@router.post("/signup")
async def sign_up(user_details:dict[str,str], client:Client =  Depends(get_db_client)):
    """
        sign up a user\\
        user_details example: {email: example@email.com, password: password123, name:username}
    """
    client.auth.sign_up({
        "email":user_details['email'],
        "password": user_details['password'],
        "options":{
            "data":{"name":user_details['name']}
        }
    })

@router.post("/signin")
async def sign_in(user_details, client:Client =  Depends(get_db_client)):
    """
        sign in a user \\
        user_details example: {email: example@email.com, password: password123}
    """
    client.auth.sign_in_with_password({
        "email":user_details['email'],
        "password": user_details['password']
    })

@router.post("/signout")
async def sign_out(client:Client =  Depends(get_db_client)):
    """
        sign out a user
    """
    client.auth.sign_out()

@router.get('/users')
async def get_all_users(client:Client = Depends(get_db_client)):
    try:
        response =(
            client.table(USER_TABLE)
            .select('*')
            .limit(100)
            .execute()
        )
        return {"data": response.data}
    except APIError as e:
        raise HTTPException(status_code=400,detail=str(e.message))

@router.get("/")
async def get_user(user = Depends(get_current_user), client:Client = Depends(get_db_client)):
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
async def update_user(data:userInput, user = Depends(get_current_user), client:Client = Depends(get_db_client)):
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
async def delete_user(user = Depends(get_current_user), client:Client = Depends(get_db_client)):
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
