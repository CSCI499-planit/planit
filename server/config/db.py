"""
    supabase database config
"""
import os
from dotenv import load_dotenv
from supabase import create_client, Client
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

load_dotenv()

url = os.getenv('SUPABASE_URL','')
key = os.getenv('SUPABASE_KEY','')

supabase: Client = create_client(url,key)

_bearer = HTTPBearer()

def get_db_client() -> Client:
    supabase = create_client(url,key)
    return supabase

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(_bearer)):
    try:
        response = supabase.auth.get_user(credentials.credentials)
        if not response or not response.user:
            raise ValueError
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return response