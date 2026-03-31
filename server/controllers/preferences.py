"""
    user preferences functions
"""
from server.config.db import supabase

PREFERENCE_TABLE = 'user_preference'

def post_preference(data, client = supabase):
    """
        post user preference data
    """
    response = (
        client.table(PREFERENCE_TABLE)
        .insert(data)
        .execute()
    )
    return response

def get_preference(user_id, client = supabase):
    """
        get user's preference form
    """
    response = (
        client.table(PREFERENCE_TABLE)
        .select('*')
        .eq('user_id',user_id)
        .execute
    )
    return response

def update_preference(user_id, data, client = supabase):
    """
        update user's preference
    """
    response = (
        client.table(PREFERENCE_TABLE)
        .update(data)
        .eq('user_id',user_id)
        .execute()
    )
    return response

def delete_preference(user_id,client = supabase):
    """
        delete user's preference data
    """
    response = (
        client.table(PREFERENCE_TABLE)
        .delete()
        .eq('user_id',user_id)
        .execute
    )
    return response
