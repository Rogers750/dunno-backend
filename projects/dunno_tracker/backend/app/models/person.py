from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel


class PersonCreate(BaseModel):
    person_id: str
    properties: Optional[dict[str, Any]] = {}


class PersonUpdate(BaseModel):
    properties: dict[str, Any]


class Person(BaseModel):
    id: str
    person_id: str
    properties: dict
    created_at: datetime
    updated_at: Optional[datetime]
