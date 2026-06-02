from fastapi import APIRouter, Depends, HTTPException
from app.auth import get_project_id
from app.repositories import get_repo
from app.models.person import Person, PersonCreate, PersonUpdate

router = APIRouter(prefix="/api/v1/people", tags=["people"])


@router.put("", response_model=Person)
async def create_person(payload: PersonCreate, project_id: str = Depends(get_project_id)):
    return get_repo().upsert_person(project_id, payload.person_id, payload.properties)


@router.get("", response_model=list[Person])
async def list_people(project_id: str = Depends(get_project_id)):
    return get_repo().list_people(project_id)


@router.get("/{person_id}", response_model=Person)
async def get_person(person_id: str, project_id: str = Depends(get_project_id)):
    person = get_repo().get_person(project_id, person_id)
    if not person:
        raise HTTPException(status_code=404, detail={"type": "person-not-found"})
    return person


@router.put("/{person_id}", response_model=Person)
async def update_person(person_id: str, payload: PersonUpdate, project_id: str = Depends(get_project_id)):
    repo = get_repo()
    existing = repo.get_person(project_id, person_id)
    if not existing:
        raise HTTPException(status_code=404, detail={"type": "person-not-found"})
    merged = {**(existing.get("properties") or {}), **payload.properties}
    return repo.update_person(existing["id"], merged)
