from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from database.supabase_client import supabase
from models.auth import (
    RegisterRequest,
    LoginRequest,
    OtpSendRequest,
    OtpVerifyRequest,
    AuthResponse,
    UserResponse,
)

router = APIRouter()
security = HTTPBearer()


def _get_profile_username(user_id: str) -> str:
    result = supabase.table("profiles").select("username").eq("id", user_id).single().execute()
    return result.data.get("username", "") if result.data else ""


@router.post("/register", response_model=AuthResponse)
async def register(payload: RegisterRequest):
    username = payload.username.strip().lower()

    existing = supabase.table("profiles").select("id").eq("username", username).execute()
    if existing.data:
        raise HTTPException(status_code=400, detail="Username already taken")

    try:
        result = supabase.auth.sign_up({
            "email": payload.email,
            "password": payload.password,
        })
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not result.user:
        raise HTTPException(status_code=400, detail="Registration failed")

    user = result.user
    session = result.session

    try:
        supabase.table("profiles").insert({
            "id": user.id,
            "username": username,
            "email": payload.email,
        }).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to create profile")

    return AuthResponse(
        access_token=session.access_token if session else "",
        user=UserResponse(id=user.id, email=user.email or payload.email, username=username),
    )


@router.post("/login", response_model=AuthResponse)
async def login(payload: LoginRequest):
    try:
        result = supabase.auth.sign_in_with_password({
            "email": payload.email,
            "password": payload.password,
        })
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not result.user or not result.session:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    user = result.user
    username = _get_profile_username(user.id)

    return AuthResponse(
        access_token=result.session.access_token,
        user=UserResponse(id=user.id, email=user.email or payload.email, username=username),
    )


@router.post("/otp/send")
async def send_otp(payload: OtpSendRequest):
    try:
        supabase.auth.sign_in_with_otp({
            "email": payload.email,
            "options": {"should_create_user": False},
        })
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"message": "One-time code sent to your email"}


@router.post("/otp/verify", response_model=AuthResponse)
async def verify_otp(payload: OtpVerifyRequest):
    try:
        result = supabase.auth.verify_otp({
            "email": payload.email,
            "token": payload.otp,
            "type": "email",
        })
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid or expired code")

    if not result.user or not result.session:
        raise HTTPException(status_code=400, detail="OTP verification failed")

    user = result.user
    username = _get_profile_username(user.id)

    return AuthResponse(
        access_token=result.session.access_token,
        user=UserResponse(id=user.id, email=user.email or payload.email, username=username),
    )


@router.post("/google", response_model=UserResponse)
async def google_oauth(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        result = supabase.auth.get_user(credentials.credentials)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    if not result.user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = result.user
    user_id = user.id
    email = user.email or ""

    existing = supabase.table("profiles").select("id, username, email").eq("id", user_id).execute()
    if existing.data:
        profile = existing.data[0]
        return UserResponse(id=profile["id"], email=profile["email"] or email, username=profile["username"])

    base = email.split("@")[0].lower()
    username = "".join(c for c in base if c.isalnum())
    candidate = username
    suffix = 1
    while supabase.table("profiles").select("id").eq("username", candidate).execute().data:
        candidate = f"{username}{suffix}"
        suffix += 1

    try:
        supabase.table("profiles").insert({
            "id": user_id,
            "username": candidate,
            "email": email,
        }).execute()
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to create profile")

    return UserResponse(id=user_id, email=email, username=candidate)


@router.get("/me", response_model=UserResponse)
async def me(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        result = supabase.auth.get_user(credentials.credentials)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    if not result.user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = result.user
    username = _get_profile_username(user.id)

    return UserResponse(id=user.id, email=user.email or "", username=username)
