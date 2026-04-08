"""
    supabase database config
"""
import os
from dotenv import load_dotenv
from supabase import create_client, Client
from fastapi import HTTPException, status

load_dotenv()

url = os.getenv('SUPABASE_URL','')
key = os.getenv('SUPABASE_KEY','')

supabase: Client = create_client(url,key)

def get_db_client() -> Client:
    """
        create connection to supabase database
    """
    supabase = create_client(url,key)
    return supabase

async def get_current_user():
    user = supabase.auth.get_user()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user