from collections import defaultdict
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends
from app.auth import get_project_id
from app.repositories import get_repo

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


@router.get("")
async def get_dashboard(project_id: str = Depends(get_project_id), days: int = 30, agent_name: str | None = None):
    repo = get_repo()
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    agent_id = None
    if agent_name:
        agent = repo.get_agent(project_id, agent_name)
        agent_id = agent["id"] if agent else None

    events = repo.list_events_in_range(project_id, since, agent_id)
    sessions = repo.list_sessions_in_range(project_id, since, agent_id)

    avg_latency = (
        sum(e.get("latency_ms") or 0 for e in events if e.get("latency_ms")) /
        max(1, sum(1 for e in events if e.get("latency_ms")))
    ) if events else 0

    by_day: dict[str, int] = defaultdict(int)
    for e in events:
        day = str(e["created_at"])[:10]
        by_day[day] += 1
    chart_data = [{"date": d, "events": c} for d, c in sorted(by_day.items())]

    session_ids = [str(s["id"]) for s in sessions]
    resolution_rate = None
    correction_rate = None
    intent_breakdown = []

    if session_ids:
        res_data = repo.get_resolution_data(session_ids)
        if res_data:
            resolution_rate = round(sum(1 for r in res_data if r["resolved"]) / len(res_data) * 100, 1)

        corrected_ids = repo.get_correction_session_ids(session_ids)
        correction_rate = round(len(corrected_ids) / len(session_ids) * 100, 1)

        intent_breakdown = repo.get_intent_weights(session_ids)

    return {
        "total_events": len(events),
        "total_sessions": len(sessions),
        "total_people": repo.count_people(project_id),
        "total_agents": repo.count_agents(project_id),
        "avg_latency_ms": round(avg_latency, 1),
        "resolution_rate": resolution_rate,
        "correction_rate": correction_rate,
        "intent_breakdown": intent_breakdown,
        "chart_data": chart_data,
    }


@router.get("/api-keys")
async def list_api_keys(project_id: str = Depends(get_project_id)):
    return get_repo().list_api_keys(project_id)


@router.post("/api-keys")
async def create_api_key(name: str, project_id: str = Depends(get_project_id)):
    from app.auth import generate_api_key
    raw_key, prefix, key_hash = generate_api_key()
    get_repo().insert_api_key(project_id, name, prefix, key_hash)
    return {"key": raw_key, "prefix": prefix, "name": name}


@router.delete("/api-keys/{key_id}")
async def revoke_api_key(key_id: str, project_id: str = Depends(get_project_id)):
    get_repo().revoke_api_key(project_id, key_id)
    return {"status": "revoked"}
