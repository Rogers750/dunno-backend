import hashlib
from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def _hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


async def get_project_id(api_key: str = Security(api_key_header)) -> str:
    if not api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key required")

    from app.repositories import get_repo
    repo = get_repo()
    key_hash = _hash_key(api_key)
    result = repo.get_api_key(key_hash)

    if not result or result.get("revoked_at"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or revoked API key")

    repo.touch_api_key(result["id"])
    return result["project_id"]


def generate_api_key() -> tuple[str, str, str]:
    """Returns (full_key, prefix, hash)"""
    import secrets
    raw = "dn_live_" + secrets.token_urlsafe(32)
    prefix = raw[:16]
    key_hash = _hash_key(raw)
    return raw, prefix, key_hash
