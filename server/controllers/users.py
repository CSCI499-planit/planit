"""
    user route functions
"""
from server.config.db import supabase

USER_TABLE = 'users'

def create_user(data, client = supabase):
    """
        create user
    """
    response = (
        client.table(USER_TABLE)
        .insert(data)
        .execute()
    )
    return response

def get_user(user_id, client = supabase):
    """
        get user data
    """
    response = (
        client.table(USER_TABLE)
        .select('*')
        .eq('id', user_id)
        .execute()
    )
    return response

def update_user(user_id, data, client = supabase):
    """
        update user data
    """
    response = (
        client.table(USER_TABLE)
        .update(data)
        .eq('id', user_id)
        .execute()
    )
    return response

def delete_user(user_id, client = supabase):
    """
        delete user data
    """
    response = (
        client.table(USER_TABLE)
        .delete()
        .eq('id', user_id)
        .execute()
    )
    return response
