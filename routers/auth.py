import uuid
import logging
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from database.supabase_client import supabase, supabase_admin
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

    existing = supabase.table("profiles").select("id, username, email, status").eq("id", user.id).execute()
    if existing.data:
        username = existing.data[0]["username"]
        status = existing.data[0].get("status", "onboarding")
        logger.info(f"[verification/verify] existing profile username={username} status={status}")
    else:
        base = email.split("@")[0].lower()
        username = "".join(c for c in base if c.isalnum())
        candidate = username
        suffix = 1
        while supabase.table("profiles").select("id").eq("username", candidate).execute().data:
            candidate = f"{username}{suffix}"
            suffix += 1
        username = candidate
        status = "onboarding"
        try:
            supabase.table("profiles").insert({"id": user.id, "username": username, "email": email, "status": status}).execute()
            logger.info(f"[verification/verify] new profile created username={username}")
        except Exception as e:
            logger.error(f"[verification/verify] failed to create profile: {e}")
            raise HTTPException(status_code=500, detail="Failed to create profile")

    return AuthResponse(
        access_token=result.session.access_token,
        user=UserResponse(id=user.id, email=email, username=username, status=status),
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

    existing = supabase.table("profiles").select("id, username, email, status").eq("id", user.id).execute()
    if existing.data:
        profile = existing.data[0]
        logger.info(f"[google] existing profile username={profile['username']}")
        return UserResponse(id=profile["id"], email=profile["email"] or email, username=profile["username"], status=profile.get("status", "onboarding"))

    base = email.split("@")[0].lower()
    username = "".join(c for c in base if c.isalnum())
    candidate = username
    suffix = 1
    while supabase.table("profiles").select("id").eq("username", candidate).execute().data:
        candidate = f"{username}{suffix}"
        suffix += 1

    try:
        supabase.table("profiles").insert({"id": user.id, "username": candidate, "email": email, "status": "onboarding"}).execute()
        logger.info(f"[google] profile created username={candidate}")
    except Exception as e:
        logger.error(f"[google] failed to insert profile: {e}")
        raise HTTPException(status_code=500, detail="Failed to create profile")

    return UserResponse(id=user.id, email=email, username=candidate, status="onboarding")


DEV_EMAIL = "sagarsinghraw77@gmail.com"


@router.post("/dev-login", response_model=AuthResponse)
async def dev_login():
    try:
        result = supabase_admin.auth.admin.generate_link({
            "type": "magiclink",
            "email": DEV_EMAIL,
        })
    except Exception as e:
        logger.error(f"[dev-login] generate_link failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    hashed_token = result.properties.hashed_token if result.properties else None
    if not hashed_token:
        raise HTTPException(status_code=500, detail="Failed to generate token")

    try:
        verified = supabase.auth.verify_otp({
            "token_hash": hashed_token,
            "type": "magiclink",
        })
    except Exception as e:
        logger.error(f"[dev-login] verify failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    if not verified.user or not verified.session:
        raise HTTPException(status_code=500, detail="Dev login failed")

    user = verified.user
    existing = supabase.table("profiles").select("id, username, email, status").eq("id", user.id).execute()
    if existing.data:
        username = existing.data[0]["username"]
        status = existing.data[0].get("status", "onboarding")
    else:
        username = "sagarrawal"
        status = "onboarding"
        supabase.table("profiles").insert({"id": user.id, "username": username, "email": DEV_EMAIL, "status": status}).execute()

    logger.info(f"[dev-login] success id={user.id} status={status}")
    return AuthResponse(
        access_token=verified.session.access_token,
        user=UserResponse(id=user.id, email=DEV_EMAIL, username=username, status=status),
    )


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
    existing = supabase.table("profiles").select("id, username, email, status").eq("id", user.id).execute()
    username = existing.data[0]["username"] if existing.data else ""
    status = existing.data[0].get("status", "onboarding") if existing.data else "onboarding"
    logger.info(f"[me] id={user.id} username={username} status={status}")
    return UserResponse(id=user.id, email=user.email or "", username=username, status=status)
