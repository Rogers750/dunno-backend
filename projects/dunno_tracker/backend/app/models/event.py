from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel


class MessagePayload(BaseModel):
    role: str
    content: Optional[str] = None
    tool_calls: Optional[list[dict]] = None
    tool_call_id: Optional[str] = None


class EventProperties(BaseModel):
    model: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    latency_ms: Optional[int] = None
    messages: Optional[list[dict]] = None
    tool_calls: Optional[list[dict]] = None
    extra: Optional[dict[str, Any]] = None


class EventCreate(BaseModel):
    event_name: str
    properties: EventProperties
    session: str
    fingerprint_id: str
    agent: Optional[str] = None
    agent_version: Optional[str] = None
    person: Optional[str] = None


class Event(BaseModel):
    id: str
    event_name: str
    properties: dict
    model: Optional[str]
    input_tokens: Optional[int]
    output_tokens: Optional[int]
    latency_ms: Optional[int]
    created_at: datetime
    session_id: Optional[str]
    agent_id: Optional[str]
    person_id: Optional[str]
