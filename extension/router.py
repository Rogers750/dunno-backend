import logging
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from database.supabase_client import supabase
from extension.crew import find_element

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


class DOMElement(BaseModel):
    index: int
    tag: str
    text: str = ""
    aria: str = ""


class FindElementRequest(BaseModel):
    elements: list[DOMElement]
    instruction: str          # plain English: "click the Easy Apply button"


# ── POST /browser/find_element ────────────────────────────────────────────────

@router.post("/find_element")
async def browser_find_element(
    payload: FindElementRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    General DOM-based element finder.

    Extension sends all visible clickable elements + a plain-English instruction.
    Returns the index of the element to click — no screenshots, no coordinates.

    Works for any instruction on any page:
      "click the Easy Apply button"
      "click the Message button for John Smith"
      "find the search box"
      "click the Submit button"
    """
    _get_user(credentials)

    if not payload.elements:
        raise HTTPException(status_code=400, detail="elements list is empty")
    if not payload.instruction or not payload.instruction.strip():
        raise HTTPException(status_code=400, detail="instruction is required")

    elements = [el.model_dump() for el in payload.elements]

    result = await find_element(elements=elements, instruction=payload.instruction)
    return result
