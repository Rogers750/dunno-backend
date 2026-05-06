from typing import Optional, List, Literal
from pydantic import BaseModel, Field


# ── CTC ──────────────────────────────────────────────────────────────────────

class CTCUpdate(BaseModel):
    current_base_in_lakhs: float = Field(gt=0)
    expected_base_in_lakhs: float = Field(gt=0)


# ── Job Preferences ───────────────────────────────────────────────────────────

class JobPreferencesUpdate(BaseModel):
    preferred_locations: Optional[List[str]] = None   # ["Bangalore", "Remote", "Mumbai"]
    company_types: Optional[List[str]] = None          # ["startup", "mnc", "product", "service"]
    min_experience: Optional[float] = None             # years — entry bar only


# ── Agent output models (enforced via output_pydantic) ────────────────────────

class ScoreBreakdown(BaseModel):
    role: float
    skills: float
    experience: float
    education: float
    company_type: float
    compensation: Optional[float] = None


class MatchResult(BaseModel):
    match_score: float
    score_breakdown: ScoreBreakdown


class CompanyInfo(BaseModel):
    glassdoor_rating: Optional[float] = None
    description: Optional[str] = None
    culture_notes: Optional[str] = None
    size: Optional[str] = None
    founded: Optional[str] = None


class ProjectSuggestion(BaseModel):
    name: str
    description: str
    difficulty: Literal["easy", "medium", "hard"]
    ai_build_time: str
    why_relevant: str


class ProjectSuggestions(BaseModel):
    suggestions: List[ProjectSuggestion]


# ── API response models ───────────────────────────────────────────────────────

class JobListingResponse(BaseModel):
    id: str
    title: str
    company: str
    location: Optional[str] = None
    url: str
    platform: str
    description: Optional[str] = None
    salary_range: Optional[str] = None
    posted_at: Optional[str] = None


class MatchedJobSummary(BaseModel):
    id: str
    job: JobListingResponse
    match_score: float
    score_breakdown: Optional[ScoreBreakdown] = None
    company_info: Optional[CompanyInfo] = None
    status: str


class MatchedJobDetail(MatchedJobSummary):
    resume_json: Optional[dict] = None
    cover_letter: Optional[str] = None
    project_suggestions: Optional[List[ProjectSuggestion]] = None
