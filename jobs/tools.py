import os
import json
import hashlib
import logging
from typing import Optional, Type

from pydantic import BaseModel, Field
from crewai.tools import BaseTool
from apify_client import ApifyClient

from database.supabase_client import supabase_admin

logger = logging.getLogger(__name__)

# ── Apify actor IDs (override via env if you swap actors) ────────────────────
# These point to commonly used public actors on Apify. Verify/update IDs in
# your Apify console if a different actor version is preferred.
_LINKEDIN_ACTOR  = os.getenv("APIFY_LINKEDIN_ACTOR",  "curious_coder/linkedin-jobs-scraper")
_NAUKRI_ACTOR    = os.getenv("APIFY_NAUKRI_ACTOR",    "bibhu/naukri-jobs-scraper")
_WELLFOUND_ACTOR = os.getenv("APIFY_WELLFOUND_ACTOR", "bebity/wellfound-jobs-scraper")
_INSTAHYRE_ACTOR = os.getenv("APIFY_INSTAHYRE_ACTOR", "dhrumil/instahyre-jobs-scraper")
_GLASSDOOR_ACTOR = os.getenv("APIFY_GLASSDOOR_ACTOR", "bebity/glassdoor-companies-scraper")


# ── Shared helpers ────────────────────────────────────────────────────────────

def _compute_job_hash(company: str, title: str, url: str) -> str:
    raw = company.lower() + title.lower() + url
    return hashlib.md5(raw.encode()).hexdigest()


def _upsert_job(
    title: str,
    company: str,
    url: str,
    platform: str,
    location: Optional[str] = None,
    description: Optional[str] = None,
    salary_range: Optional[str] = None,
    posted_at: Optional[str] = None,
    expires_at: Optional[str] = None,
) -> Optional[str]:
    """Insert job into job_listings. On duplicate job_hash → return existing id."""
    if not title or not company or not url:
        return None

    job_hash = _compute_job_hash(company, title, url)

    existing = supabase_admin.table("job_listings").select("id").eq("job_hash", job_hash).execute()
    if existing.data:
        return existing.data[0]["id"]

    try:
        result = supabase_admin.table("job_listings").insert({
            "job_hash": job_hash,
            "title": title,
            "company": company,
            "location": location,
            "url": url,
            "platform": platform,
            "description": description,
            "salary_range": salary_range,
            "posted_at": posted_at,
            "expires_at": expires_at,
            "is_live": True,
        }).execute()
        return result.data[0]["id"] if result.data else None
    except Exception as e:
        logger.error(f"[tools/_upsert_job] insert failed: {e}")
        return None


def _apify_client() -> ApifyClient:
    token = os.getenv("APIFY_TOKEN")
    if not token:
        raise ValueError("APIFY_TOKEN is not set")
    return ApifyClient(token)


# ── Input schema shared by all job search tools ───────────────────────────────

class JobSearchInput(BaseModel):
    search_query: str = Field(
        description="The job title/role plus optional skills to search for. "
                    "E.g. 'Senior Data Engineer Python Spark India'"
    )


# ── LinkedIn Jobs Tool ────────────────────────────────────────────────────────

class LinkedInJobsTool(BaseTool):
    name: str = "LinkedIn Jobs Search"
    description: str = (
        "Search LinkedIn for live job listings matching a role/skill query. "
        "Saves new jobs to the database and returns their IDs. "
        "Input: job title + key skills + location, e.g. 'Senior Data Engineer Spark India'."
    )
    args_schema: Type[BaseModel] = JobSearchInput

    def _run(self, search_query: str) -> str:
        try:
            client = _apify_client()
            encoded = search_query.replace(" ", "%20")
            search_url = f"https://www.linkedin.com/jobs/search/?keywords={encoded}&location=India&f_TPR=r604800"
            run = client.actor(_LINKEDIN_ACTOR).call(
                run_input={
                    "urls": [search_url],
                    "resultsPerPage": 10,
                },
                timeout_secs=300,
            )
            items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
            job_ids = []
            for item in items:
                jid = _upsert_job(
                    title=item.get("title", ""),
                    company=item.get("companyName", item.get("company", "")),
                    url=item.get("jobUrl", item.get("url", "")),
                    platform="linkedin",
                    location=item.get("location"),
                    description=item.get("description"),
                    salary_range=item.get("salary"),
                    posted_at=item.get("postedAt"),
                )
                if jid:
                    job_ids.append(jid)
            logger.info(f"[linkedin_tool] saved {len(job_ids)} jobs")
            return f"LinkedIn: saved {len(job_ids)} jobs. IDs: {','.join(job_ids)}"
        except Exception as e:
            logger.error(f"[linkedin_tool] error: {e}")
            return f"LinkedIn search failed: {str(e)}"


# ── Naukri Jobs Tool ──────────────────────────────────────────────────────────

class NaukriJobsTool(BaseTool):
    name: str = "Naukri Jobs Search"
    description: str = (
        "Search Naukri for live job listings in India matching a role/skill query. "
        "Saves new jobs to the database and returns their IDs. "
        "Input: job title + key skills, e.g. 'Data Engineer Kafka Python'."
    )
    args_schema: Type[BaseModel] = JobSearchInput

    def _run(self, search_query: str) -> str:
        try:
            client = _apify_client()
            run = client.actor(_NAUKRI_ACTOR).call(
                run_input={
                    "keyword": search_query,
                    "location": "India",
                    "maxJobs": 25,
                },
                timeout_secs=180,
            )
            items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
            job_ids = []
            for item in items:
                jid = _upsert_job(
                    title=item.get("title", ""),
                    company=item.get("company", ""),
                    url=item.get("url", item.get("jobUrl", "")),
                    platform="naukri",
                    location=item.get("location"),
                    description=item.get("description"),
                    salary_range=item.get("salary", item.get("salaryRange")),
                    posted_at=item.get("postedDate"),
                )
                if jid:
                    job_ids.append(jid)
            logger.info(f"[naukri_tool] saved {len(job_ids)} jobs")
            return f"Naukri: saved {len(job_ids)} jobs. IDs: {','.join(job_ids)}"
        except Exception as e:
            logger.error(f"[naukri_tool] error: {e}")
            return f"Naukri search failed: {str(e)}"


# ── Wellfound Jobs Tool ───────────────────────────────────────────────────────

class WellfoundJobsTool(BaseTool):
    name: str = "Wellfound Jobs Search"
    description: str = (
        "Search Wellfound (formerly AngelList) for startup jobs matching a role/skill query. "
        "Saves new jobs to the database and returns their IDs. "
        "Input: job title + skills, e.g. 'Backend Engineer Python FastAPI'."
    )
    args_schema: Type[BaseModel] = JobSearchInput

    def _run(self, search_query: str) -> str:
        try:
            client = _apify_client()
            run = client.actor(_WELLFOUND_ACTOR).call(
                run_input={
                    "query": search_query,
                    "maxResults": 25,
                },
                timeout_secs=180,
            )
            items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
            job_ids = []
            for item in items:
                jid = _upsert_job(
                    title=item.get("title", ""),
                    company=item.get("company", item.get("companyName", "")),
                    url=item.get("url", item.get("jobUrl", "")),
                    platform="wellfound",
                    location=item.get("location"),
                    description=item.get("description"),
                    salary_range=item.get("compensation", item.get("salary")),
                    posted_at=item.get("postedAt"),
                )
                if jid:
                    job_ids.append(jid)
            logger.info(f"[wellfound_tool] saved {len(job_ids)} jobs")
            return f"Wellfound: saved {len(job_ids)} jobs. IDs: {','.join(job_ids)}"
        except Exception as e:
            logger.error(f"[wellfound_tool] error: {e}")
            return f"Wellfound search failed: {str(e)}"


# ── Instahyre Jobs Tool ───────────────────────────────────────────────────────

class InstahyrJobsTool(BaseTool):
    name: str = "Instahyre Jobs Search"
    description: str = (
        "Search Instahyre for curated tech jobs in India matching a role/skill query. "
        "Saves new jobs to the database and returns their IDs. "
        "Input: job title + skills, e.g. 'Machine Learning Engineer PyTorch'."
    )
    args_schema: Type[BaseModel] = JobSearchInput

    def _run(self, search_query: str) -> str:
        try:
            client = _apify_client()
            run = client.actor(_INSTAHYRE_ACTOR).call(
                run_input={
                    "query": search_query,
                    "maxResults": 25,
                },
                timeout_secs=180,
            )
            items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
            job_ids = []
            for item in items:
                jid = _upsert_job(
                    title=item.get("title", ""),
                    company=item.get("company", ""),
                    url=item.get("url", item.get("jobUrl", "")),
                    platform="instahyre",
                    location=item.get("location"),
                    description=item.get("description"),
                    salary_range=item.get("salary"),
                    posted_at=item.get("postedAt"),
                )
                if jid:
                    job_ids.append(jid)
            logger.info(f"[instahyre_tool] saved {len(job_ids)} jobs")
            return f"Instahyre: saved {len(job_ids)} jobs. IDs: {','.join(job_ids)}"
        except Exception as e:
            logger.error(f"[instahyre_tool] error: {e}")
            return f"Instahyre search failed: {str(e)}"


# ── Glassdoor Company Tool ────────────────────────────────────────────────────

class GlassdoorInput(BaseModel):
    company_name: str = Field(description="The exact company name to look up on Glassdoor.")


class GlassdoorTool(BaseTool):
    name: str = "Glassdoor Company Lookup"
    description: str = (
        "Look up a company on Glassdoor to get rating, culture notes, size, and founding year. "
        "Returns null values if the company is not found. "
        "Input: exact company name, e.g. 'Dezerv'."
    )
    args_schema: Type[BaseModel] = GlassdoorInput

    def _run(self, company_name: str) -> str:
        try:
            client = _apify_client()
            run = client.actor(_GLASSDOOR_ACTOR).call(
                run_input={
                    "query": company_name,
                    "maxResults": 1,
                },
                timeout_secs=120,
            )
            items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
            if not items:
                return json.dumps({
                    "glassdoor_rating": None,
                    "description": None,
                    "culture_notes": None,
                    "size": None,
                    "founded": None,
                })
            item = items[0]
            result = {
                "glassdoor_rating": item.get("overallRating", item.get("rating")),
                "description": item.get("description", item.get("companyDescription")),
                "culture_notes": item.get("cultureAndValues", item.get("culture")),
                "size": item.get("size", item.get("employeeCount")),
                "founded": str(item.get("foundedYear", item.get("founded", ""))),
            }
            return json.dumps(result)
        except Exception as e:
            logger.error(f"[glassdoor_tool] error: {e}")
            return json.dumps({
                "glassdoor_rating": None,
                "description": None,
                "culture_notes": None,
                "size": None,
                "founded": None,
            })
