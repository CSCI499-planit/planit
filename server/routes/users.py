"""
    user route to store user account details
"""
from fastapi import APIRouter, HTTPException, Depends
from postgrest.exceptions import APIError
from supabase import Client, create_client
from server.config.db import get_db_client, get_current_user, url, key
from server.models.users import userInput

USER_TABLE = "user"
router = APIRouter(prefix="/user", tags=["user"])


def _user_exists(user_id: str, client: Client) -> bool:
    return len(client.table(USER_TABLE).select("id").eq("id", user_id).execute().data) > 0


@router.post("/signup")
async def sign_up(user_details: dict[str, str], client: Client = Depends(get_db_client)):
    """
    Sign up a new user.
    Body: { email, password, name }
    Returns: { access_token, user_id }
    """
    try:
        res = client.auth.sign_up({
            "email":    user_details["email"],
            "password": user_details["password"],
            "options":  {"data": {"name": user_details.get("name", "")}},
        })
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    user_id = str(res.user.id)

    # Upsert into the custom user table. The anon client has no JWT at this
    # point so RLS would block the insert. Use the new user's session token
    # to satisfy the auth.uid() = id policy. Falls back to anon if no session
    # (email confirmation flow) — the Supabase trigger is the safety net there.
    try:
        if res.session:
            authed = create_client(url, key)
            authed.postgrest.auth(res.session.access_token)
            authed.table(USER_TABLE).upsert(
                {"id": user_id, "name": user_details.get("name", ""), "email": user_details["email"]},
                on_conflict="id",
            ).execute()
        else:
            client.table(USER_TABLE).upsert(
                {"id": user_id, "name": user_details.get("name", ""), "email": user_details["email"]},
                on_conflict="id",
            ).execute()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"User profile creation failed: {e}")

    if not res.session:
        return {"status": "confirmation_required", "user_id": user_id}

    return {"access_token": res.session.access_token, "user_id": user_id}


@router.post("/signin")
async def sign_in(user_details: dict[str, str], client: Client = Depends(get_db_client)):
    """
    Sign in an existing user.
    Body: { email, password }
    Returns: { access_token, user_id }
    """
    try:
        res = client.auth.sign_in_with_password({
            "email":    user_details["email"],
            "password": user_details["password"],
        })
        return {"access_token": res.session.access_token, "user_id": str(res.user.id)}
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.post("/signout")
async def sign_out(client: Client = Depends(get_db_client)):
    client.auth.sign_out()
    return {"status": "signed out"}


@router.get("/users")
async def get_all_users(client: Client = Depends(get_db_client)):
    try:
        response = client.table(USER_TABLE).select("*").limit(100).execute()
        return {"data": response.data}
    except APIError as e:
        raise HTTPException(status_code=400, detail=str(e.message))


@router.get("/")
async def get_user(user=Depends(get_current_user), client: Client = Depends(get_db_client)):
    try:
        response = client.table(USER_TABLE).select("*").eq("id", user.user.id).execute()
        return {"status": "success", "data": response.data}
    except APIError as e:
        raise HTTPException(status_code=400, detail=str(e.message))


@router.put("/")
async def update_user(data: userInput, user=Depends(get_current_user), client: Client = Depends(get_db_client)):
    try:
        if not _user_exists(str(user.user.id), client):
            raise HTTPException(status_code=404, detail="User not found.")
        response = client.table(USER_TABLE).update(data.model_dump()).eq("id", user.user.id).execute()
        return {"message": "user updated", "data": response.data}
    except APIError as e:
        raise HTTPException(status_code=400, detail=str(e.message))


@router.delete("/")
async def delete_user(user=Depends(get_current_user), client: Client = Depends(get_db_client)):
    try:
        if not _user_exists(str(user.user.id), client):
            raise HTTPException(status_code=404, detail="User not found.")
        response = client.table(USER_TABLE).delete().eq("id", user.user.id).execute()
        return {"message": "user deleted", "data": response.data}
    except APIError as e:
        raise HTTPException(status_code=400, detail=str(e.message))
