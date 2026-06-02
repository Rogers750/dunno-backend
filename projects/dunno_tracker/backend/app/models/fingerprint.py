from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class FingerprintCreate(BaseModel):
    language: str
    language_version: Optional[str] = None
    sdk_version: Optional[str] = None
    system: str
    git_commit: Optional[str] = None
    git_branch: Optional[str] = None
    git_tag: Optional[str] = None


class Fingerprint(BaseModel):
    fingerprint_id: str
    language: str
    language_version: Optional[str]
    sdk_version: Optional[str]
    system: str
    created_at: datetime
