import logging
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

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


class ReferralRequest(BaseModel):
    profile_text: str   # raw text pasted from LinkedIn (Cmd+A, Cmd+C)
    company: str
    role: str = ""


# ── POST /referral/generate ───────────────────────────────────────────────────

@router.post("/generate")
async def generate_referral(
    payload: ReferralRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Generate a personalised referral request message.

    User pastes raw LinkedIn profile text (Cmd+A → Cmd+C on the profile page).
    DeepSeek parses it, finds shared connections with the user's background,
    and writes a targeted DM.

    Returns:
    - message: the referral message to send
    - connections_found: shared connections used to personalise the message
    - recipient_name: name extracted from the pasted text
    """
    user = _get_user(credentials)

    if not payload.profile_text or len(payload.profile_text.strip()) < 50:
        raise HTTPException(
            status_code=400,
            detail="Profile text is too short. Please paste the full LinkedIn profile (Cmd+A → Cmd+C on the profile page).",
        )

    portfolio = (
        supabase_admin.table("portfolios")
        .select("generated_content, target_roles")
        .eq("user_id", user.id)
        .eq("published", True)
        .limit(1)
        .execute()
    )
    if not portfolio.data or not portfolio.data[0].get("generated_content"):
        raise HTTPException(
            status_code=400,
            detail="No published portfolio found. Complete onboarding first.",
        )

    gen_content = portfolio.data[0]["generated_content"]

    role = payload.role.strip()
    if not role:
        target_roles = portfolio.data[0].get("target_roles") or []
        role = target_roles[0] if target_roles else ""

    from referral.crew import generate_referral_message
    result = generate_referral_message(
        profile_text=payload.profile_text,
        company=payload.company,
        role=role,
        gen_content=gen_content,
    )

    return result
