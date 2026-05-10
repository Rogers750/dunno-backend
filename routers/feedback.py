import logging
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Literal

from database.supabase_client import supabase, supabase_admin

logger = logging.getLogger(__name__)

router = APIRouter()
security = HTTPBearer(auto_error=False)


def _get_user(credentials: HTTPAuthorizationCredentials):
    if not credentials:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    try:
        result = supabase.auth.get_user(credentials.credentials)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    if not result.user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return result.user


class FeedbackRequest(BaseModel):
    message: str
    type: Literal["feedback", "feature_request", "bug"] = "feedback"


# ── POST /feedback ────────────────────────────────────────────────────────────

@router.post("")
async def submit_feedback(
    payload: FeedbackRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Submit feedback or a feature request. Stores user id, name, email, and message."""
    user = _get_user(credentials)

    if not payload.message or not payload.message.strip():
        raise HTTPException(status_code=400, detail="message is required")

    profile = (
        supabase_admin.table("profiles")
        .select("username, email")
        .eq("id", user.id)
        .limit(1)
        .execute()
    )
    name = profile.data[0].get("username") if profile.data else None
    email = profile.data[0].get("email") if profile.data else user.email

    result = supabase_admin.table("feedback").insert({
        "user_id": user.id,
        "name": name,
        "email": email,
        "type": payload.type,
        "message": payload.message.strip(),
    }).execute()

    logger.info(f"[feedback] user={user.id} type={payload.type}")
    return result.data[0] if result.data else {"status": "saved"}
