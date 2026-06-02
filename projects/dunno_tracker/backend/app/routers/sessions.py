from fastapi import APIRouter, Depends, HTTPException
from app.auth import get_project_id
from app.repositories import get_repo

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


@router.get("")
async def list_sessions(project_id: str = Depends(get_project_id), agent_name: str | None = None, limit: int = 50, offset: int = 0):
    repo = get_repo()
    agent_id = None
    if agent_name:
        agent = repo.get_agent(project_id, agent_name)
        agent_id = agent["id"] if agent else None
    return repo.list_sessions(project_id, agent_id, limit, offset)


@router.get("/{session_id}")
async def get_session(session_id: str, project_id: str = Depends(get_project_id)):
    repo = get_repo()
    session = repo.get_session(project_id, session_id)
    if not session:
        raise HTTPException(status_code=404, detail={"type": "session-not-found"})

    session_db_id = session["id"]
    events = repo.get_session_events_with_messages(session_db_id)
    intents = repo.get_session_intents(session_db_id)
    corrections = repo.get_session_corrections(session_db_id)
    resolution = repo.get_session_resolution(session_db_id)

    total_input_tokens = sum(e.get("input_tokens") or 0 for e in events)
    total_output_tokens = sum(e.get("output_tokens") or 0 for e in events)
    total_latency_ms = sum(e.get("latency_ms") or 0 for e in events)

    return {
        **session,
        "events": events,
        "intents": intents,
        "session_path": [i["intent"] for i in intents],
        "corrections": corrections,
        "resolution": resolution,
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "total_tokens": total_input_tokens + total_output_tokens,
        "total_latency_ms": total_latency_ms,
    }
