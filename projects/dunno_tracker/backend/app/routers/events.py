from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from app.auth import get_project_id
from app.repositories import get_repo
from app.models.event import Event, EventCreate
from app.analysis import analyze_session

router = APIRouter(prefix="/api/v1/events", tags=["events"])


def _resolve_agent(repo, project_id: str, agent_name: str | None) -> str | None:
    if not agent_name:
        return None
    agent = repo.upsert_agent(project_id, agent_name)
    return agent["id"] if agent else None


def _resolve_agent_version(repo, agent_id: str | None, version_name: str | None) -> str | None:
    if not agent_id or not version_name:
        return None
    version = repo.get_agent_version(agent_id, version_name)
    return version["id"] if version else None


def _resolve_person(repo, project_id: str, person_id_str: str | None) -> str | None:
    if not person_id_str:
        return None
    person = repo.upsert_person(project_id, person_id_str)
    return person["id"] if person else None


def _resolve_fingerprint(repo, project_id: str, fingerprint_id: str) -> str | None:
    return repo.get_fingerprint_db_id(project_id, fingerprint_id)


@router.post("", response_model=Event)
async def create_event(payload: EventCreate, background_tasks: BackgroundTasks, project_id: str = Depends(get_project_id)):
    repo = get_repo()

    fingerprint_db_id = _resolve_fingerprint(repo, project_id, payload.fingerprint_id)
    if not fingerprint_db_id:
        raise HTTPException(status_code=404, detail={"type": "fingerprint-not-found"})

    agent_db_id = _resolve_agent(repo, project_id, payload.agent)
    agent_version_db_id = _resolve_agent_version(repo, agent_db_id, payload.agent_version)
    person_db_id = _resolve_person(repo, project_id, payload.person)
    session_db_id = repo.upsert_session(project_id, payload.session, person_db_id, agent_db_id)

    props = payload.properties
    event = repo.insert_event({
        "project_id": project_id,
        "session_id": session_db_id,
        "agent_id": agent_db_id,
        "agent_version_id": agent_version_db_id,
        "person_id": person_db_id,
        "fingerprint_id": fingerprint_db_id,
        "event_name": payload.event_name,
        "properties": props.model_dump(exclude_none=True),
        "model": props.model,
        "input_tokens": props.input_tokens,
        "output_tokens": props.output_tokens,
        "latency_ms": props.latency_ms,
    })

    if props.messages:
        messages_rows = [
            {
                "event_id": event["id"],
                "role": m.get("role", "user"),
                "content": m.get("content"),
                "tool_calls": m.get("tool_calls"),
                "tool_call_id": m.get("tool_call_id"),
            }
            for m in props.messages
        ]
        repo.insert_messages(messages_rows)

    # Trigger analysis every 3rd event (debounce handled inside analyze_session)
    event_count = repo.count_session_events(session_db_id)
    if event_count >= 1 and event_count % 3 == 0:
        background_tasks.add_task(analyze_session, get_repo(), session_db_id)

    return event


@router.get("", response_model=list[Event])
async def list_events(project_id: str = Depends(get_project_id), session_id: str | None = None, limit: int = 50):
    repo = get_repo()
    session_db_id = None
    if session_id:
        session = repo.get_session(project_id, session_id)
        session_db_id = session["id"] if session else None
    return repo.list_events(project_id, session_db_id, limit)


@router.get("/{event_id}", response_model=Event)
async def get_event(event_id: str, project_id: str = Depends(get_project_id)):
    event = get_repo().get_event(project_id, event_id)
    if not event:
        raise HTTPException(status_code=404, detail={"type": "event-not-found"})
    return event
