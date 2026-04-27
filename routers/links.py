import logging
import httpx
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from database.supabase_client import supabase

logger = logging.getLogger(__name__)

router = APIRouter()
security = HTTPBearer(auto_error=False)


class LinkRequest(BaseModel):
    url: str


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


def _parse_github_url(url: str) -> tuple[str, str]:
    """Returns (type, api_url): type is 'github_profile' or 'github_repo'"""
    url = url.rstrip("/")
    parts = url.replace("https://github.com/", "").split("/")
    if len(parts) == 1:
        return "github_profile", f"https://api.github.com/users/{parts[0]}"
    elif len(parts) == 2:
        return "github_repo", f"https://api.github.com/repos/{parts[0]}/{parts[1]}"
    raise ValueError("Invalid GitHub URL")


async def _fetch_github(api_url: str) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.get(api_url, headers={"Accept": "application/vnd.github+json"}, timeout=10)
        resp.raise_for_status()
        return resp.json()


def _upsert_link(user_id: str, link_type: str, url: str, fetched: dict) -> str:
    existing = supabase.table("links").select("id").eq("user_id", user_id).eq("url", url).execute()
    if existing.data:
        supabase.table("links").update({"fetched": fetched, "type": link_type}).eq("id", existing.data[0]["id"]).execute()
        return existing.data[0]["id"]
    result = supabase.table("links").insert({"user_id": user_id, "type": link_type, "url": url, "fetched": fetched}).execute()
    return result.data[0]["id"]


@router.post("/github")
async def add_github_link(
    payload: LinkRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    user = _get_user(credentials)
    logger.info(f"[links/github] user={user.id} url={payload.url}")

    try:
        link_type, api_url = _parse_github_url(payload.url)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid GitHub URL")

    try:
        fetched = await _fetch_github(api_url)
        logger.info(f"[links/github] fetched {link_type} from {api_url}")
    except Exception as e:
        logger.error(f"[links/github] GitHub fetch failed: {e}")
        raise HTTPException(status_code=400, detail="Failed to fetch GitHub data")

    link_id = _upsert_link(user.id, link_type, payload.url, fetched)
    saved_repos = []

    if link_type == "github_profile":
        username = fetched.get("login")
        try:
            repos = await _fetch_github(f"https://api.github.com/users/{username}/repos?per_page=100&sort=updated")
            logger.info(f"[links/github] fetched {len(repos)} repos for {username}")
            for repo in repos:
                repo_url = repo.get("html_url", "")
                repo_id = _upsert_link(user.id, "github_repo", repo_url, repo)
                saved_repos.append({"id": repo_id, "url": repo_url, "name": repo.get("name")})
        except Exception as e:
            logger.warning(f"[links/github] failed to fetch repos: {e}")

    logger.info(f"[links/github] done link_id={link_id} repos={len(saved_repos)}")
    return {"id": link_id, "type": link_type, "url": payload.url, "repos_saved": len(saved_repos), "repos": saved_repos}


@router.get("/me")
async def get_links(credentials: HTTPAuthorizationCredentials = Depends(security)):
    user = _get_user(credentials)
    result = supabase.table("links").select("id, type, url, included, created_at").eq("user_id", user.id).execute()
    return result.data or []


@router.get("/repos")
async def get_repos(credentials: HTTPAuthorizationCredentials = Depends(security)):
    user = _get_user(credentials)
    result = supabase.table("links").select("id, url, fetched, included").eq("user_id", user.id).eq("type", "github_repo").execute()

    repos = []
    for row in result.data or []:
        f = row.get("fetched") or {}
        repos.append({
            "id": row["id"],
            "included": row["included"],
            "name": f.get("name"),
            "description": f.get("description"),
            "url": f.get("html_url"),
            "stars": f.get("stargazers_count", 0),
            "language": f.get("language"),
            "topics": f.get("topics", []),
        })

    repos.sort(key=lambda r: r["stars"], reverse=True)
    logger.info(f"[links/repos] user={user.id} repos={len(repos)}")
    return repos


@router.patch("/{link_id}/toggle")
async def toggle_link(
    link_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    user = _get_user(credentials)
    existing = supabase.table("links").select("id, included").eq("id", link_id).eq("user_id", user.id).execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Link not found")

    new_val = not existing.data[0]["included"]
    supabase.table("links").update({"included": new_val}).eq("id", link_id).execute()
    logger.info(f"[links/toggle] link_id={link_id} included={new_val}")
    return {"id": link_id, "included": new_val}
