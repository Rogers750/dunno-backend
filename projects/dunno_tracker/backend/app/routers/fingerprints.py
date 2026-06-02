import uuid
from fastapi import APIRouter, Depends
from app.auth import get_project_id
from app.repositories import get_repo
from app.models.fingerprint import Fingerprint, FingerprintCreate

router = APIRouter(prefix="/api/v1/fingerprints", tags=["fingerprints"])


@router.put("", response_model=Fingerprint)
async def create_fingerprint(payload: FingerprintCreate, project_id: str = Depends(get_project_id)):
    fingerprint_id = str(uuid.uuid4())
    return get_repo().insert_fingerprint(project_id, fingerprint_id, payload.model_dump())
