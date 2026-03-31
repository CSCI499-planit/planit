"""
    user ratings functions
"""
from server.config.db import supabase

RATINGS_TABLE = 'user_likes'

def post_rating(data, client = supabase):
    """
        post user ratings
    """
    response = (
        client.table(RATINGS_TABLE)
        .insert(data)
        .execute()
    )
    return response

def get_rating(user_id, client = supabase):
    """
        get user ratings
    """
    response = (
        client.table(RATINGS_TABLE)
        .select('*')
        .eq('user_id',user_id)
        .execute()
    )
    return response

def update_rating(user_id, data, client = supabase):
    """
        update user rating
    """
    response = (
        client.table(RATINGS_TABLE)
        .update(data)
        .eq('user_id',user_id)
        .execute()
    )
    return response

def delete_rating(user_id, client = supabase):
    """
        delete user ratings
    """
    response = (
        client.table(RATINGS_TABLE)
        .delete()
        .eq('user_id',user_id)
        .execute()
    )
    return response
