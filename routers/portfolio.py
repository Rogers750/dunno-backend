"""
portfolio.py — Full portfolio generation, editing, photo upload, and GitHub refresh.

Endpoints:
  POST   /portfolio/generate              — DeepSeek AI → strict JSON portfolio
  GET    /portfolio/me                    — Get saved portfolio
  PATCH  /portfolio/me/section            — Edit a specific section in-place
  PATCH  /portfolio/template              — Save selected template (+ theme)
  POST   /portfolio/publish               — Toggle published flag
  POST   /portfolio/photo                 — Upload profile photo
  DELETE /portfolio/photo                 — Remove profile photo
  POST   /portfolio/repos/refresh         — Re-fetch GitHub, surface new repos
  PATCH  /portfolio/repos/{link_id}       — Toggle repo inclusion
  GET    /portfolio/{username}            — Public: fetch published portfolio
"""

import io
import json
import logging
import httpx
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Any, Optional
import os
from dotenv import load_dotenv

from database.supabase_client import supabase, supabase_admin, create_user_client

load_dotenv()

logger = logging.getLogger(__name__)
router = APIRouter()
security = HTTPBearer(auto_error=False)

DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = "deepseek-chat"

ALLOWED_SECTIONS = {"personal", "social", "skills", "experience", "projects", "education"}


# ─── Auth helpers ────────────────────────────────────────────────────────────

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


def _get_user_client(credentials: HTTPAuthorizationCredentials):
    return create_user_client(credentials.credentials)


# ─── Pydantic models ──────────────────────────────────────────────────────────

class SectionPatchRequest(BaseModel):
    section: str          # e.g. "personal", "skills", "experience"
    data: Any             # the updated value for that section


class TemplatePatchRequest(BaseModel):
    selected_template: str        # "executive_minimal" | "modern_dark" | "creative_dev"
    theme_color: Optional[str] = None
    theme_category: Optional[str] = None


class PublishRequest(BaseModel):
    published: bool


class GenerateRequest(BaseModel):
    target_roles: Optional[list[str]] = None   # override stored target_roles
    extra_context: Optional[str] = None         # freeform extra info from user


# ─── DeepSeek caller ─────────────────────────────────────────────────────────

async def _call_deepseek(system_prompt: str, user_message: str, max_tokens: int = 4096) -> str:
    if not DEEPSEEK_API_KEY:
        raise HTTPException(status_code=500, detail="DEEPSEEK_API_KEY not configured")

    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.3,
        "response_format": {"type": "json_object"},
    }

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=90) as client:
        resp = await client.post(
            f"{DEEPSEEK_BASE_URL}/chat/completions",
            json=payload,
            headers=headers,
        )

    if resp.status_code != 200:
        logger.error(f"[deepseek] error {resp.status_code}: {resp.text[:500]}")
        raise HTTPException(status_code=502, detail=f"DeepSeek API error: {resp.status_code}")

    body = resp.json()
    return body["choices"][0]["message"]["content"]


# ─── Deep analysis prompt ─────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an elite technical writer and career strategist who builds world-class developer portfolio content.

Your job: Convert raw resume text + GitHub data + context into a STRICT JSON portfolio object.

OUTPUT RULES — follow exactly, no exceptions:
1. Return ONLY valid JSON. No markdown fences, no commentary, no preamble.
2. Follow the schema 100% — no extra keys, no missing keys.
3. If a field cannot be filled, use "" (string) or [] (array). Never null, never omit.
4. Keep ALL text concise, punchy, and impact-driven.

ANALYSIS DEPTH REQUIREMENTS:
- QUANTIFY everything: extract ALL numbers, percentages, dollar amounts, scale figures (e.g. "reduced latency by 40%", "scaled to 100M events/day", "saved $300K/year"). If a number is vague in the resume, keep it as written.
- EVIDENCE-BASED SKILLS: rank skills by how many times they appear with context (not just listed). A skill mentioned in 3 job descriptions beats one mentioned once.
- IMPACT HIGHLIGHTS: for each experience, identify the top 3 most impressive outcomes (with numbers). These go in highlights[].
- PROJECT RELEVANCE: if target_roles are provided, select/rank projects that best match those roles. Highlight the tech + impact that matters most for those roles.
- BIO SYNTHESIS: write a 2–3 sentence bio that captures: seniority level, core specialisation, career arc, and ONE signature achievement. Avoid generic phrases like "passionate about", "team player", "results-driven".
- TITLE INFERENCE: derive the most accurate job title from the most recent role + seniority signals in the resume.
- GITHUB INTEGRATION: pull project names, descriptions, stars, languages, and topics from GitHub data. Merge with resume projects where they overlap (don't duplicate). Surface repos with high stars or unique tech as standalone projects.
- SKILL GROUPING: group skills into logical categories (e.g. "Languages", "Data Engineering", "ML / AI", "Cloud & DevOps", "Databases", "Tools"). Deduplicate. Sort by proficiency evidence.

SCHEMA (return exactly this structure):
{
  "personal": {
    "name": "Full Name",
    "title": "Senior Data Engineer",
    "bio": "2-3 sentence punchy bio",
    "location": "City, Country",
    "email": "email@example.com",
    "phone": "+1-234-567-8900",
    "website": "https://example.com"
  },
  "social": {
    "github": "https://github.com/username",
    "linkedin": "https://linkedin.com/in/username",
    "twitter": "",
    "other": []
  },
  "skills": [
    {
      "category": "Languages",
      "items": ["Python", "SQL", "Go"]
    }
  ],
  "experience": [
    {
      "company": "Company Name",
      "role": "Senior Engineer",
      "duration": "Jan 2022 – Present",
      "description": "One-line summary of team/product scope",
      "highlights": [
        "Reduced pipeline latency by 60% by migrating to Apache Flink",
        "Owned data platform serving 50M+ daily active users",
        "Led a team of 4 engineers across 3 time zones"
      ]
    }
  ],
  "projects": [
    {
      "name": "Project Name",
      "description": "What it does and why it matters — one punchy sentence",
      "tech": ["Python", "FastAPI", "Redis"],
      "github": "https://github.com/user/repo",
      "live": "https://project.com",
      "highlights": [
        "Processing 10K+ requests/sec",
        "Used by 500+ users in 3 countries"
      ]
    }
  ],
  "education": [
    {
      "institution": "University Name",
      "degree": "B.Tech in Computer Science",
      "duration": "2016 – 2020"
    }
  ],
  "target_roles": ["Senior Data Engineer", "MLOps Engineer"]
}

- target_roles: infer 2-4 most suitable job titles from the resume, experience level, and skills.
  If target_roles are explicitly provided in the prompt, use those instead.
Do not deviate from this schema under any circumstances."""


def _build_user_message(
    resume_text: str,
    github_data: list[dict],
    target_roles: list[str],
    extra_context: str,
) -> str:
    parts = []

    parts.append("=== RESUME TEXT ===")
    parts.append(resume_text.strip() if resume_text else "(No resume text available)")

    if target_roles:
        parts.append(f"\n=== TARGET ROLES ===\n{', '.join(target_roles)}")

    if github_data:
        parts.append("\n=== GITHUB REPOSITORIES ===")
        for repo in github_data:
            f = repo.get("fetched") or {}
            parts.append(
                f"- {f.get('full_name', repo.get('url', ''))}\n"
                f"  Description: {f.get('description') or '(none)'}\n"
                f"  Language: {f.get('language') or '—'} | Stars: {f.get('stargazers_count', 0)} | Forks: {f.get('forks_count', 0)}\n"
                f"  Topics: {', '.join(f.get('topics', [])) or '—'}\n"
                f"  URL: {f.get('html_url', repo.get('url', ''))}"
            )

    if extra_context:
        parts.append(f"\n=== ADDITIONAL CONTEXT FROM USER ===\n{extra_context.strip()}")

    parts.append(
        "\n=== INSTRUCTION ===\n"
        "Analyse ALL content above. Apply deep analysis per the schema rules. "
        "Return the strict JSON portfolio object now."
    )

    return "\n".join(parts)


# ─── GitHub helpers ───────────────────────────────────────────────────────────

async def _fetch_github_repo(api_url: str) -> dict:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            api_url,
            headers={"Accept": "application/vnd.github+json"},
        )
        resp.raise_for_status()
        return resp.json()


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.post("/generate")
async def generate_portfolio(
    payload: GenerateRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Pull resume text + included GitHub repos for the user, send to DeepSeek
    with a deep-analysis prompt, save generated_content to portfolios table.
    """
    user = _get_user(credentials)
    user_client = _get_user_client(credentials)
    logger.info(f"[portfolio/generate] user={user.id}")

    # 1. Fetch resume raw text
    resume_row = user_client.table("resumes").select("raw_text, parsed").eq("user_id", user.id).execute()
    resume_text = ""
    if resume_row.data:
        resume_text = resume_row.data[0].get("raw_text") or ""
        logger.info(f"[portfolio/generate] resume chars={len(resume_text)}")

    # 2. Fetch included GitHub repos
    links_row = user_client.table("links").select("url, type, fetched, included").eq("user_id", user.id).execute()
    github_repos = [r for r in (links_row.data or []) if r.get("included") and r.get("type") == "github_repo"]
    logger.info(f"[portfolio/generate] included_repos={len(github_repos)}")

    # 3. Fetch or load target_roles from portfolios table
    portfolio_row = user_client.table("portfolios").select("id, target_roles, theme_color, theme_category").eq("user_id", user.id).execute()
    stored_roles = []
    if portfolio_row.data:
        stored_roles = portfolio_row.data[0].get("target_roles") or []

    target_roles = payload.target_roles if payload.target_roles is not None else stored_roles

    if not resume_text and not github_repos:
        raise HTTPException(status_code=400, detail="No resume or GitHub data found. Upload a resume or add GitHub links first.")

    # 4. Call DeepSeek
    user_message = _build_user_message(
        resume_text=resume_text,
        github_data=github_repos,
        target_roles=target_roles,
        extra_context=payload.extra_context or "",
    )

    logger.info(f"[portfolio/generate] calling DeepSeek model={DEEPSEEK_MODEL}")
    raw_json_str = await _call_deepseek(SYSTEM_PROMPT, user_message, max_tokens=4096)

    try:
        generated_content = json.loads(raw_json_str)
    except json.JSONDecodeError as e:
        logger.error(f"[portfolio/generate] JSON parse error: {e}\nraw={raw_json_str[:300]}")
        raise HTTPException(status_code=502, detail="DeepSeek returned invalid JSON. Try again.")

    # 5. Fill any missing top-level keys with safe empty defaults
    EMPTY_DEFAULTS: dict = {
        "personal": {"name": "", "title": "", "bio": "", "location": "", "email": "", "phone": "", "website": ""},
        "social": {"github": "", "linkedin": "", "twitter": "", "other": []},
        "skills": [],
        "experience": [],
        "projects": [],
        "education": [],
        "target_roles": [],
    }
    for key, default in EMPTY_DEFAULTS.items():
        if key not in generated_content:
            logger.warning(f"[portfolio/generate] DeepSeek omitted '{key}', filling with empty default")
            generated_content[key] = default

    # Use DeepSeek-inferred target_roles if caller did not explicitly provide them
    if not payload.target_roles:
        target_roles = generated_content.get("target_roles") or target_roles
        logger.info(f"[portfolio/generate] inferred target_roles={target_roles}")

    # 6. Upsert portfolios row
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()

    if portfolio_row.data:
        portfolio_id = portfolio_row.data[0]["id"]
        user_client.table("portfolios").update({
            "generated_content": generated_content,
            "generated_at": now,
            "target_roles": target_roles,
        }).eq("id", portfolio_id).execute()
    else:
        result = user_client.table("portfolios").insert({
            "user_id": user.id,
            "generated_content": generated_content,
            "generated_at": now,
            "target_roles": target_roles,
        }).execute()
        portfolio_id = result.data[0]["id"]

    # 7. Auto-publish + mark profile status → ready
    user_client.table("portfolios").update({"published": True}).eq("id", portfolio_id).execute()
    supabase_admin.table("profiles").update({"status": "ready"}).eq("id", user.id).execute()

    logger.info(f"[portfolio/generate] done portfolio_id={portfolio_id}")
    return {
        "portfolio_id": portfolio_id,
        "generated_content": generated_content,
        "repos_used": len(github_repos),
        "target_roles": target_roles,
    }


@router.get("/me")
async def get_portfolio(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Return the user's full portfolio row including generated_content."""
    user = _get_user(credentials)
    user_client = _get_user_client(credentials)

    row = user_client.table("portfolios").select("*").eq("user_id", user.id).execute()
    if not row.data:
        raise HTTPException(status_code=404, detail="No portfolio found. Run /portfolio/generate first.")

    profile_row = user_client.table("profiles").select("photo_url, username").eq("id", user.id).execute()
    profile = profile_row.data[0] if profile_row.data else {}

    return {**row.data[0], "photo_url": profile.get("photo_url"), "username": profile.get("username")}


@router.patch("/me/section")
async def patch_section(
    payload: SectionPatchRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Update a single section of generated_content.
    section must be one of: personal, social, skills, experience, projects, education
    data is the new value for that section (replaces the whole section).
    """
    if payload.section not in ALLOWED_SECTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid section '{payload.section}'. Must be one of: {', '.join(ALLOWED_SECTIONS)}",
        )

    user = _get_user(credentials)
    user_client = _get_user_client(credentials)

    row = user_client.table("portfolios").select("id, generated_content").eq("user_id", user.id).execute()
    if not row.data:
        raise HTTPException(status_code=404, detail="No portfolio found. Generate first.")

    portfolio_id = row.data[0]["id"]
    content = row.data[0].get("generated_content") or {}
    content[payload.section] = payload.data

    user_client.table("portfolios").update({"generated_content": content}).eq("id", portfolio_id).execute()
    logger.info(f"[portfolio/patch_section] user={user.id} section={payload.section}")
    return {"portfolio_id": portfolio_id, "section": payload.section, "updated": True}


@router.patch("/template")
async def save_template(
    payload: TemplatePatchRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Save the user's selected template and optionally theme_color / theme_category."""
    valid_templates = {"executive_minimal", "modern_dark", "creative_dev"}
    if payload.selected_template not in valid_templates:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid template. Must be one of: {', '.join(valid_templates)}",
        )

    user = _get_user(credentials)
    user_client = _get_user_client(credentials)

    update: dict = {"selected_template": payload.selected_template}
    if payload.theme_color:
        update["theme_color"] = payload.theme_color
    if payload.theme_category:
        update["theme_category"] = payload.theme_category

    row = user_client.table("portfolios").select("id").eq("user_id", user.id).execute()
    if not row.data:
        # Create minimal portfolio row so template can be saved before generation
        result = user_client.table("portfolios").insert({
            "user_id": user.id,
            **update,
        }).execute()
        portfolio_id = result.data[0]["id"]
    else:
        portfolio_id = row.data[0]["id"]
        user_client.table("portfolios").update(update).eq("id", portfolio_id).execute()

    logger.info(f"[portfolio/template] user={user.id} template={payload.selected_template}")
    return {"portfolio_id": portfolio_id, **update}


@router.post("/publish")
async def publish_portfolio(
    payload: PublishRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Toggle published status."""
    user = _get_user(credentials)
    user_client = _get_user_client(credentials)

    row = user_client.table("portfolios").select("id").eq("user_id", user.id).execute()
    if not row.data:
        raise HTTPException(status_code=404, detail="No portfolio found. Generate first.")

    portfolio_id = row.data[0]["id"]
    user_client.table("portfolios").update({"published": payload.published}).eq("id", portfolio_id).execute()

    if payload.published:
        supabase_admin.table("profiles").update({"status": "ready"}).eq("id", user.id).execute()

    logger.info(f"[portfolio/publish] user={user.id} published={payload.published}")
    return {"portfolio_id": portfolio_id, "published": payload.published}


# ─── Photo upload ─────────────────────────────────────────────────────────────

PHOTO_BUCKET = "avatars"
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_PHOTO_MB = 5


@router.post("/photo")
async def upload_photo(
    file: UploadFile = File(...),
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Upload a profile photo. Stored in Supabase storage 'avatars' bucket."""
    user = _get_user(credentials)

    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail=f"Unsupported image type: {file.content_type}. Use JPEG, PNG, WebP, or GIF.")

    contents = await file.read()
    if len(contents) > MAX_PHOTO_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"File too large. Max {MAX_PHOTO_MB}MB.")

    ext = file.content_type.split("/")[-1].replace("jpeg", "jpg")
    storage_path = f"{user.id}/avatar.{ext}"

    try:
        supabase_admin.storage.from_(PHOTO_BUCKET).upload(
            storage_path,
            contents,
            {"content-type": file.content_type, "upsert": "true"},
        )
        photo_url = supabase_admin.storage.from_(PHOTO_BUCKET).get_public_url(storage_path)
        logger.info(f"[portfolio/photo] uploaded path={storage_path}")
    except Exception as e:
        logger.error(f"[portfolio/photo] upload failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to upload photo. Check bucket permissions.")

    supabase_admin.table("profiles").update({"photo_url": photo_url}).eq("id", user.id).execute()
    return {"photo_url": photo_url}


@router.delete("/photo")
async def delete_photo(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Remove the profile photo from storage and clear photo_url in profiles."""
    user = _get_user(credentials)

    for ext in ["jpg", "png", "webp", "gif"]:
        storage_path = f"{user.id}/avatar.{ext}"
        try:
            supabase_admin.storage.from_(PHOTO_BUCKET).remove([storage_path])
        except Exception:
            pass  # OK if the file didn't exist

    supabase_admin.table("profiles").update({"photo_url": None}).eq("id", user.id).execute()
    logger.info(f"[portfolio/photo] deleted photo user={user.id}")
    return {"deleted": True}


# ─── GitHub repo refresh ──────────────────────────────────────────────────────

@router.post("/repos/refresh")
async def refresh_github_repos(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Re-fetch all GitHub repos from any stored github_profile links.
    Returns repos that are NEW (not already in links table) so the user
    can decide whether to include them.
    """
    user = _get_user(credentials)
    user_client = _get_user_client(credentials)

    # Get all stored profile links
    profile_links = (
        user_client.table("links")
        .select("id, url, fetched")
        .eq("user_id", user.id)
        .eq("type", "github_profile")
        .execute()
    )

    if not profile_links.data:
        raise HTTPException(status_code=400, detail="No GitHub profile linked. Add one via POST /links/github first.")

    # Get already-known repo URLs
    existing_repos = (
        user_client.table("links")
        .select("url")
        .eq("user_id", user.id)
        .eq("type", "github_repo")
        .execute()
    )
    known_urls = {r["url"] for r in (existing_repos.data or [])}

    new_repos = []
    updated_count = 0

    for profile in profile_links.data:
        username = (profile.get("fetched") or {}).get("login")
        if not username:
            url_parts = profile["url"].rstrip("/").split("/")
            username = url_parts[-1] if url_parts else None
        if not username:
            continue

        logger.info(f"[portfolio/repos/refresh] fetching repos for {username}")
        try:
            repos = await _fetch_github_repo(
                f"https://api.github.com/users/{username}/repos?per_page=100&sort=updated"
            )
        except Exception as e:
            logger.warning(f"[portfolio/repos/refresh] failed for {username}: {e}")
            continue

        for repo in repos:
            repo_url = repo.get("html_url", "")
            if repo_url in known_urls:
                # Refresh stored data with latest GitHub info — user-scoped so RLS applies
                try:
                    user_client.table("links").update({"fetched": repo}).eq("user_id", user.id).eq("url", repo_url).execute()
                    updated_count += 1
                except Exception:
                    pass
            else:
                # Genuinely new repo — insert with included=False so user can opt-in
                try:
                    result = user_client.table("links").insert({
                        "user_id": user.id,
                        "type": "github_repo",
                        "url": repo_url,
                        "fetched": repo,
                        "included": False,
                    }).execute()
                    new_repos.append({
                        "id": result.data[0]["id"],
                        "name": repo.get("name"),
                        "description": repo.get("description"),
                        "url": repo_url,
                        "stars": repo.get("stargazers_count", 0),
                        "language": repo.get("language"),
                        "topics": repo.get("topics", []),
                        "included": False,
                    })
                    known_urls.add(repo_url)
                except Exception as e:
                    logger.warning(f"[portfolio/repos/refresh] insert failed for {repo_url}: {e}")

    logger.info(f"[portfolio/repos/refresh] new={len(new_repos)} updated={updated_count}")
    return {
        "new_repos": new_repos,
        "new_count": len(new_repos),
        "refreshed_count": updated_count,
        "message": f"Found {len(new_repos)} new repo(s). Toggle inclusion with PATCH /portfolio/repos/{{id}}.",
    }


@router.patch("/repos/{link_id}")
async def toggle_repo_inclusion(
    link_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Toggle whether a GitHub repo is included in portfolio generation."""
    user = _get_user(credentials)
    user_client = _get_user_client(credentials)

    row = (
        user_client.table("links")
        .select("id, included, fetched")
        .eq("id", link_id)
        .eq("user_id", user.id)
        .eq("type", "github_repo")
        .execute()
    )
    if not row.data:
        raise HTTPException(status_code=404, detail="Repo not found")

    current = row.data[0]
    new_val = not current["included"]
    user_client.table("links").update({"included": new_val}).eq("id", link_id).execute()

    f = current.get("fetched") or {}
    logger.info(f"[portfolio/repos/toggle] link_id={link_id} included={new_val}")
    return {
        "id": link_id,
        "included": new_val,
        "name": f.get("name"),
        "url": f.get("html_url"),
    }


# ─── Public portfolio endpoint ────────────────────────────────────────────────

@router.get("/{username}")
async def get_public_portfolio(username: str, response: Response):
    """
    Public endpoint — returns the published portfolio for a given username.
    No auth required. Used by the /[username] page on the frontend.
    Cached for 60 seconds by browsers and CDN.
    """
    profile = (
        supabase.table("profiles")
        .select("id, username, photo_url")
        .eq("username", username)
        .execute()
    )
    if not profile.data:
        raise HTTPException(status_code=404, detail=f"No user found with username '{username}'")

    user_id = profile.data[0]["id"]
    photo_url = profile.data[0].get("photo_url")

    portfolio = (
        supabase.table("portfolios")
        .select("generated_content, theme_color, theme_category, selected_template, published, generated_at")
        .eq("user_id", user_id)
        .eq("published", True)
        .execute()
    )
    if not portfolio.data:
        raise HTTPException(status_code=404, detail=f"Portfolio for '{username}' is not published yet.")

    response.headers["Cache-Control"] = "public, max-age=60"
    return {
        "username": username,
        "photo_url": photo_url,
        **portfolio.data[0],
    }
