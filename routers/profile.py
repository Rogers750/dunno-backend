import logging
from typing import Optional, List, Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from database.supabase_client import supabase, supabase_admin

logger = logging.getLogger(__name__)
router = APIRouter()
security = HTTPBearer(auto_error=False)


# ── Auth helper ───────────────────────────────────────────────────────────────

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


# ── Patch payload models ──────────────────────────────────────────────────────

class BasicsUpdate(BaseModel):
    name: Optional[str] = None
    username: Optional[str] = None
    bio: Optional[str] = None


class TargetRolesUpdate(BaseModel):
    target_roles: List[str]


class PreferencesUpdate(BaseModel):
    preferred_locations: Optional[List[str]] = None
    company_types: Optional[List[str]] = None
    current_salary: Optional[float] = None      # LPA
    expected_salary: Optional[float] = None     # LPA


class ExperienceUpdate(BaseModel):
    experience: List[Any]


class EducationUpdate(BaseModel):
    education: List[Any]


class SkillsUpdate(BaseModel):
    skills: Any  # dict with languages/frameworks/tools/concepts


class ProjectsUpdate(BaseModel):
    projects: List[Any]


class SocialUpdate(BaseModel):
    linkedin: Optional[str] = None
    github: Optional[str] = None
    twitter: Optional[str] = None
    medium: Optional[str] = None
    portfolio: Optional[str] = None
    website: Optional[str] = None


class AchievementsUpdate(BaseModel):
    achievements: List[Any]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _current_role(experience: list) -> dict:
    """Extract current company + role from experience list."""
    for exp in experience:
        if isinstance(exp, dict):
            end = exp.get("endSortDate") or exp.get("endDate") or ""
            if end in ("9999-12", "Present", "present", ""):
                return {"current_company": exp.get("company"), "current_role": exp.get("role")}
    if experience and isinstance(experience[0], dict):
        return {
            "current_company": experience[0].get("company"),
            "current_role": experience[0].get("role"),
        }
    return {"current_company": None, "current_role": None}


def _extract_social(gen_content: dict) -> dict:
    personal = gen_content.get("personal") or {}
    social = gen_content.get("social") or {}
    merged = {**social, **personal}
    keys = ["linkedin", "github", "twitter", "medium", "portfolio", "website"]
    return {k: merged.get(k) for k in keys}


def _get_portfolio_row(user_id: str) -> tuple[Optional[str], dict]:
    """Returns (portfolio_id, generated_content). id is None if no portfolio yet."""
    row = supabase_admin.table("portfolios").select("id, generated_content, target_roles").eq("user_id", user_id).execute()
    if not row.data:
        return None, {}
    return row.data[0]["id"], row.data[0].get("generated_content") or {}


def _patch_generated_content(portfolio_id: str, key: str, value: Any) -> None:
    """Fetch current generated_content, replace one top-level key, write back."""
    row = supabase_admin.table("portfolios").select("generated_content").eq("id", portfolio_id).execute()
    content = (row.data[0].get("generated_content") or {}) if row.data else {}
    content[key] = value
    supabase_admin.table("portfolios").update({"generated_content": content}).eq("id", portfolio_id).execute()


# ── GET /profile/me ───────────────────────────────────────────────────────────

@router.get("/me")
async def get_profile(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Return all profile data as structured widgets for the frontend."""
    user = _get_user(credentials)

    profile_row = supabase_admin.table("profiles").select(
        "username, email, photo_url, ctc, job_preferences"
    ).eq("id", user.id).execute()

    if not profile_row.data:
        raise HTTPException(status_code=404, detail="Profile not found")

    profile = profile_row.data[0]
    ctc = profile.get("ctc") or {}
    prefs = profile.get("job_preferences") or {}

    portfolio_row = supabase_admin.table("portfolios").select(
        "id, generated_content, target_roles"
    ).eq("user_id", user.id).execute()

    gen = {}
    target_roles = []
    if portfolio_row.data:
        gen = portfolio_row.data[0].get("generated_content") or {}
        target_roles = portfolio_row.data[0].get("target_roles") or []

    personal = gen.get("personal") or {}
    experience = gen.get("experience") or []

    return {
        "basics": {
            "name": personal.get("name"),
            "username": profile.get("username"),
            "email": profile.get("email") or user.email,
            "photo_url": profile.get("photo_url"),
            "bio": personal.get("bio") or personal.get("summary"),
            **_current_role(experience),
        },
        "target_roles": target_roles,
        "preferences": {
            "preferred_locations": prefs.get("preferred_locations") or [],
            "company_types": prefs.get("company_types") or [],
            "current_salary": ctc.get("current_base_in_lakhs"),
            "expected_salary": ctc.get("expected_base_in_lakhs"),
        },
        "experience": experience,
        "education": gen.get("education") or [],
        "skills": gen.get("skills") or {},
        "projects": gen.get("projects") or [],
        "social": _extract_social(gen),
        "achievements": gen.get("achievements") or [],
        "certifications": gen.get("certifications") or [],
        "publications": gen.get("publications") or [],
    }


# ── PATCH /profile/me/basics ──────────────────────────────────────────────────

@router.patch("/me/basics")
async def patch_basics(
    payload: BasicsUpdate,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    user = _get_user(credentials)
    update: dict = {}

    if payload.username is not None:
        taken = supabase_admin.table("profiles").select("id").eq("username", payload.username).neq("id", user.id).execute()
        if taken.data:
            raise HTTPException(status_code=409, detail="Username already taken")
        update["username"] = payload.username

    # bio lives in generated_content.personal — handle separately
    bio = payload.bio
    name = payload.name

    if update:
        supabase_admin.table("profiles").update(update).eq("id", user.id).execute()

    if bio is not None or name is not None:
        portfolio_id, gen = _get_portfolio_row(user.id)
        if portfolio_id:
            personal = gen.get("personal") or {}
            if bio is not None:
                personal["bio"] = bio
            if name is not None:
                personal["name"] = name
            gen["personal"] = personal
            supabase_admin.table("portfolios").update({"generated_content": gen}).eq("id", portfolio_id).execute()

    logger.info(f"[profile/basics] user={user.id} updated={list(payload.model_dump(exclude_none=True).keys())}")
    return {"ok": True}


# ── PATCH /profile/me/target-roles ───────────────────────────────────────────

@router.patch("/me/target-roles")
async def patch_target_roles(
    payload: TargetRolesUpdate,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    user = _get_user(credentials)
    result = supabase_admin.table("portfolios").update({"target_roles": payload.target_roles}).eq("user_id", user.id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    logger.info(f"[profile/target-roles] user={user.id} roles={payload.target_roles}")
    return {"ok": True, "target_roles": payload.target_roles}


# ── PATCH /profile/me/preferences ────────────────────────────────────────────

@router.patch("/me/preferences")
async def patch_preferences(
    payload: PreferencesUpdate,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    user = _get_user(credentials)

    existing = supabase_admin.table("profiles").select("job_preferences, ctc").eq("id", user.id).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Profile not found")

    prefs = existing.data[0].get("job_preferences") or {}
    ctc = existing.data[0].get("ctc") or {}

    if payload.preferred_locations is not None:
        prefs["preferred_locations"] = payload.preferred_locations
    if payload.company_types is not None:
        prefs["company_types"] = payload.company_types
    if payload.current_salary is not None:
        ctc["current_base_in_lakhs"] = payload.current_salary
    if payload.expected_salary is not None:
        ctc["expected_base_in_lakhs"] = payload.expected_salary

    supabase_admin.table("profiles").update({"job_preferences": prefs, "ctc": ctc}).eq("id", user.id).execute()
    logger.info(f"[profile/preferences] user={user.id}")
    return {"ok": True, "preferences": {**prefs, "current_salary": ctc.get("current_base_in_lakhs"), "expected_salary": ctc.get("expected_base_in_lakhs")}}


# ── PATCH /profile/me/experience ─────────────────────────────────────────────

@router.patch("/me/experience")
async def patch_experience(
    payload: ExperienceUpdate,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    user = _get_user(credentials)
    portfolio_id, _ = _get_portfolio_row(user.id)
    if not portfolio_id:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    _patch_generated_content(portfolio_id, "experience", payload.experience)
    logger.info(f"[profile/experience] user={user.id} entries={len(payload.experience)}")
    return {"ok": True}


# ── PATCH /profile/me/education ──────────────────────────────────────────────

@router.patch("/me/education")
async def patch_education(
    payload: EducationUpdate,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    user = _get_user(credentials)
    portfolio_id, _ = _get_portfolio_row(user.id)
    if not portfolio_id:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    _patch_generated_content(portfolio_id, "education", payload.education)
    logger.info(f"[profile/education] user={user.id}")
    return {"ok": True}


# ── PATCH /profile/me/skills ──────────────────────────────────────────────────

@router.patch("/me/skills")
async def patch_skills(
    payload: SkillsUpdate,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    user = _get_user(credentials)
    portfolio_id, _ = _get_portfolio_row(user.id)
    if not portfolio_id:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    _patch_generated_content(portfolio_id, "skills", payload.skills)
    logger.info(f"[profile/skills] user={user.id}")
    return {"ok": True}


# ── PATCH /profile/me/projects ────────────────────────────────────────────────

@router.patch("/me/projects")
async def patch_projects(
    payload: ProjectsUpdate,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    user = _get_user(credentials)
    portfolio_id, _ = _get_portfolio_row(user.id)
    if not portfolio_id:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    _patch_generated_content(portfolio_id, "projects", payload.projects)
    logger.info(f"[profile/projects] user={user.id} count={len(payload.projects)}")
    return {"ok": True}


# ── PATCH /profile/me/social ─────────────────────────────────────────────────

@router.patch("/me/social")
async def patch_social(
    payload: SocialUpdate,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    user = _get_user(credentials)
    portfolio_id, gen = _get_portfolio_row(user.id)
    if not portfolio_id:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    personal = gen.get("personal") or {}
    for field, value in payload.model_dump(exclude_none=True).items():
        personal[field] = value
    gen["personal"] = personal
    supabase_admin.table("portfolios").update({"generated_content": gen}).eq("id", portfolio_id).execute()
    logger.info(f"[profile/social] user={user.id} fields={list(payload.model_dump(exclude_none=True).keys())}")
    return {"ok": True}


# ── PATCH /profile/me/achievements ───────────────────────────────────────────

@router.patch("/me/achievements")
async def patch_achievements(
    payload: AchievementsUpdate,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    user = _get_user(credentials)
    portfolio_id, _ = _get_portfolio_row(user.id)
    if not portfolio_id:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    _patch_generated_content(portfolio_id, "achievements", payload.achievements)
    logger.info(f"[profile/achievements] user={user.id}")
    return {"ok": True}
