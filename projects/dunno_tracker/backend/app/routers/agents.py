from fastapi import APIRouter, Depends, HTTPException
from app.auth import get_project_id
from app.repositories import get_repo
from app.models.agent import Agent, AgentCreate, AgentVersion, AgentVersionCreate

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])


@router.put("", response_model=Agent)
async def create_agent(payload: AgentCreate, project_id: str = Depends(get_project_id)):
    repo = get_repo()
    agent_number = repo.count_agents(project_id) + 1
    return repo.upsert_agent(project_id, payload.agent_name, payload.description, agent_number)


@router.get("", response_model=list[Agent])
async def list_agents(project_id: str = Depends(get_project_id)):
    return get_repo().list_agents(project_id)


@router.get("/{agent_name}", response_model=Agent)
async def get_agent(agent_name: str, project_id: str = Depends(get_project_id)):
    agent = get_repo().get_agent(project_id, agent_name)
    if not agent:
        raise HTTPException(status_code=404, detail={"type": "agent-not-found"})
    return agent


@router.put("/{agent_name}/agent-versions", response_model=AgentVersion)
async def create_agent_version(agent_name: str, payload: AgentVersionCreate, project_id: str = Depends(get_project_id)):
    repo = get_repo()
    agent = repo.get_agent(project_id, agent_name)
    if not agent:
        raise HTTPException(status_code=404, detail={"type": "agent-not-found"})
    version_number = repo.count_agent_versions(agent["id"]) + 1
    return repo.upsert_agent_version(agent["id"], payload.agent_version_name, payload.description, payload.model, payload.system_prompt, version_number)


@router.get("/{agent_name}/agent-versions", response_model=list[AgentVersion])
async def list_agent_versions(agent_name: str, project_id: str = Depends(get_project_id)):
    repo = get_repo()
    agent = repo.get_agent(project_id, agent_name)
    if not agent:
        raise HTTPException(status_code=404, detail={"type": "agent-not-found"})
    return repo.list_agent_versions(agent["id"])


@router.get("/{agent_name}/agent-versions/{agent_version_name}", response_model=AgentVersion)
async def get_agent_version(agent_name: str, agent_version_name: str, project_id: str = Depends(get_project_id)):
    repo = get_repo()
    agent = repo.get_agent(project_id, agent_name)
    if not agent:
        raise HTTPException(status_code=404, detail={"type": "agent-not-found"})
    version = repo.get_agent_version(agent["id"], agent_version_name)
    if not version:
        raise HTTPException(status_code=404, detail={"type": "agent-version-not-found"})
    return version
