from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class AgentCreate(BaseModel):
    agent_name: str
    description: Optional[str] = None


class AgentVersionCreate(BaseModel):
    agent_version_name: str
    description: Optional[str] = None
    model: Optional[str] = None
    system_prompt: Optional[str] = None


class Agent(BaseModel):
    id: str
    agent_name: str
    description: Optional[str]
    agent_number: Optional[int]
    created_at: datetime
    deprecated_at: Optional[datetime]


class AgentVersion(BaseModel):
    id: str
    agent_version_name: str
    description: Optional[str]
    agent_version_number: Optional[int]
    model: Optional[str]
    created_at: datetime
    deprecated_at: Optional[datetime]
