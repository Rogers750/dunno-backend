import uuid
import logging
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from database.supabase_client import supabase
from models.auth import OtpSendRequest, OtpVerifyRequest, AuthResponse, UserResponse

logger = logging.getLogger(__name__)

router = APIRouter()
security = HTTPBearer(auto_error=False)

# temporary in-memory store: session_id -> email
_otp_sessions: dict[str, str] = {}


@router.post("/verification/send")
async def send_otp(payload: OtpSendRequest):
    logger.info(f"[verification/send] email={payload.email}")
    try:
        supabase.auth.sign_in_with_otp({
            "email": payload.email,
            "options": {"should_create_user": True},
        })
    except Exception as e:
        logger.error(f"[verification/send] failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    session_id = str(uuid.uuid4())
    _otp_sessions[session_id] = payload.email
    logger.info(f"[verification/send] OTP sent, session_id={session_id}")
    return {"message": "OTP sent to your email", "session_id": session_id}


@router.post("/verification/verify", response_model=AuthResponse)
async def verify_otp(payload: OtpVerifyRequest):
    email = _otp_sessions.get(payload.session_id)
    if not email:
        logger.warning(f"[verification/verify] invalid session_id={payload.session_id}")
        raise HTTPException(status_code=400, detail="Invalid or expired session")

    logger.info(f"[verification/verify] session_id={payload.session_id} email={email}")
    try:
        result = supabase.auth.verify_otp({
            "email": email,
            "token": payload.otp,
            "type": "email",
        })
    except Exception as e:
        logger.warning(f"[verification/verify] failed: {e}")
        raise HTTPException(status_code=400, detail="Invalid or expired OTP")

    if not result.user or not result.session:
        raise HTTPException(status_code=400, detail="OTP verification failed")

    _otp_sessions.pop(payload.session_id, None)
    user = result.user
    email = user.email or email

    existing = supabase.table("profiles").select("id, username, email").eq("id", user.id).execute()
    if existing.data:
        username = existing.data[0]["username"]
        logger.info(f"[verification/verify] existing profile username={username}")
    else:
        base = email.split("@")[0].lower()
        username = "".join(c for c in base if c.isalnum())
        candidate = username
        suffix = 1
        while supabase.table("profiles").select("id").eq("username", candidate).execute().data:
            candidate = f"{username}{suffix}"
            suffix += 1
        username = candidate
        try:
            supabase.table("profiles").insert({"id": user.id, "username": username, "email": email}).execute()
            logger.info(f"[verification/verify] new profile created username={username}")
        except Exception as e:
            logger.error(f"[verification/verify] failed to create profile: {e}")
            raise HTTPException(status_code=500, detail="Failed to create profile")

    return AuthResponse(
        access_token=result.session.access_token,
        user=UserResponse(id=user.id, email=email, username=username),
    )


@router.post("/google", response_model=UserResponse)
async def google_oauth(credentials: HTTPAuthorizationCredentials = Depends(security)):
    logger.info("[google] POST /auth/google called")
    if not credentials:
        logger.warning("[google] no Authorization header")
        raise HTTPException(status_code=401, detail="Authorization header missing")

    logger.info(f"[google] token (first 20): {credentials.credentials[:20]}")
    try:
        result = supabase.auth.get_user(credentials.credentials)
    except Exception as e:
        logger.error(f"[google] get_user failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    if not result.user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = result.user
    email = user.email or ""
    logger.info(f"[google] token valid id={user.id} email={email}")

    existing = supabase.table("profiles").select("id, username, email").eq("id", user.id).execute()
    if existing.data:
        profile = existing.data[0]
        logger.info(f"[google] existing profile username={profile['username']}")
        return UserResponse(id=profile["id"], email=profile["email"] or email, username=profile["username"])

    base = email.split("@")[0].lower()
    username = "".join(c for c in base if c.isalnum())
    candidate = username
    suffix = 1
    while supabase.table("profiles").select("id").eq("username", candidate).execute().data:
        candidate = f"{username}{suffix}"
        suffix += 1

    try:
        supabase.table("profiles").insert({"id": user.id, "username": candidate, "email": email}).execute()
        logger.info(f"[google] profile created username={candidate}")
    except Exception as e:
        logger.error(f"[google] failed to insert profile: {e}")
        raise HTTPException(status_code=500, detail="Failed to create profile")

    return UserResponse(id=user.id, email=email, username=candidate)


@router.get("/me", response_model=UserResponse)
async def me(credentials: HTTPAuthorizationCredentials = Depends(security)):
    logger.info("[me] called")
    if not credentials:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    try:
        result = supabase.auth.get_user(credentials.credentials)
    except Exception as e:
        logger.error(f"[me] get_user failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    if not result.user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = result.user
    existing = supabase.table("profiles").select("id, username, email").eq("id", user.id).execute()
    username = existing.data[0]["username"] if existing.data else ""
    logger.info(f"[me] id={user.id} username={username}")
    return UserResponse(id=user.id, email=user.email or "", username=username)
