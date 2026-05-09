import os
import logging
import httpx
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from database.supabase_client import supabase

logger = logging.getLogger(__name__)

router = APIRouter()
security = HTTPBearer(auto_error=False)

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"


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


class ExtensionAIRequest(BaseModel):
    prompt: str
    system_prompt: str | None = None    # optional — extension can pass its own context
    model: str = "deepseek-chat"        # deepseek-chat | deepseek-reasoner


# ── POST /extension/ai ────────────────────────────────────────────────────────

@router.post("/ai")
async def extension_ai(
    payload: ExtensionAIRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Proxy endpoint for the browser extension.
    Takes a prompt, calls DeepSeek, returns the response.
    Requires a valid user auth token.
    """
    _get_user(credentials)

    if not payload.prompt or not payload.prompt.strip():
        raise HTTPException(status_code=400, detail="prompt is required")

    if not DEEPSEEK_API_KEY:
        raise HTTPException(status_code=500, detail="DeepSeek API key not configured")

    messages = []
    if payload.system_prompt:
        messages.append({"role": "system", "content": payload.system_prompt})
    messages.append({"role": "user", "content": payload.prompt})

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{DEEPSEEK_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": payload.model,
                    "messages": messages,
                },
            )
            response.raise_for_status()
            data = response.json()

        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})

        return {
            "response": content,
            "model": payload.model,
            "usage": {
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "total_tokens": usage.get("total_tokens"),
            },
        }

    except httpx.HTTPStatusError as e:
        logger.error(f"[extension/ai] DeepSeek error: {e.response.status_code} {e.response.text}")
        raise HTTPException(status_code=502, detail=f"DeepSeek API error: {e.response.status_code}")
    except Exception as e:
        logger.error(f"[extension/ai] unexpected error: {e}")
        raise HTTPException(status_code=500, detail="AI request failed")
