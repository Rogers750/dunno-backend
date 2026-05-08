import logging
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, HttpUrl

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
    linkedin_url: str
    company: str
    role: str


# ── POST /referral/generate ───────────────────────────────────────────────────

@router.post("/generate")
async def generate_referral(
    payload: ReferralRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Generate a personalised referral request message.

    Scrapes the given LinkedIn profile, finds shared connections with the user
    (same college, same past company), and writes a targeted DM.

    Returns:
    - message: the referral message to send
    - warning: non-null if the profile doesn't appear to work at the target company
    - connections_found: list of shared connections used to personalise the message
    - recipient_name: name extracted from the scraped profile
    """
    user = _get_user(credentials)

    # Load user's portfolio
    portfolio = (
        supabase_admin.table("portfolios")
        .select("generated_content")
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

    from referral.crew import generate_referral_message
    result = generate_referral_message(
        linkedin_url=payload.linkedin_url,
        company=payload.company,
        role=payload.role,
        gen_content=gen_content,
    )

    return result
