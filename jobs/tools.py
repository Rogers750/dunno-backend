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
_NAUKRI_ACTOR    = os.getenv("APIFY_NAUKRI_ACTOR",    "stealth_mode/naukri-jobs-search-scraper")
_GOOGLE_JOBS_ACTOR = os.getenv("APIFY_GOOGLE_JOBS_ACTOR", "bebity/google-jobs-scraper")
_GLASSDOOR_ACTOR = os.getenv("APIFY_GLASSDOOR_ACTOR", "bebity/glassdoor-companies-scraper")


# ── Shared helpers ────────────────────────────────────────────────────────────

def _pick(item: dict, keys: list[str]) -> Optional[str]:
    """Try multiple field name candidates; return first non-empty value found."""
    for k in keys:
        v = item.get(k)
        if v:
            return str(v)
    return None


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
    missing = [f for f, v in [("title", title), ("company", company), ("url", url)] if not v]
    if missing:
        logger.warning(f"[_upsert_job] skipped on {platform} — missing fields: {missing} | title={title!r} company={company!r} url={url!r}")
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
            if items:
                logger.info(f"[linkedin_tool] {len(items)} items scraped. first item: {dict(list(items[0].items())[:10])}")
            job_ids = []
            for item in items:
                jid = _upsert_job(
                    title=_pick(item, ["title", "jobTitle", "position"]),
                    company=_pick(item, ["companyName", "company", "employer"]),
                    url=_pick(item, ["link", "applyUrl", "jobUrl", "url", "jobLink"]),
                    platform="linkedin",
                    location=_pick(item, ["location", "jobLocation"]),
                    description=_pick(item, ["descriptionText", "description", "descriptionHtml"]),
                    salary_range=_pick(item, ["salaryInfo", "salary", "salaryRange", "compensation"]),
                    posted_at=_pick(item, ["postedAt", "postedDate", "datePosted"]),
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
            # stealth_mode actor takes Naukri search page URLs
            slug = search_query.lower().replace(" ", "-")
            search_url = f"https://www.naukri.com/{slug}-jobs-in-india"
            run = client.actor(_NAUKRI_ACTOR).call(
                run_input={
                    "urls": [search_url],
                    "max_items_per_url": 25,
                },
                timeout_secs=180,
            )
            items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
            if items:
                logger.info(f"[naukri_tool] {len(items)} items scraped. first item: {dict(list(items[0].items())[:10])}")
            job_ids = []
            for item in items:
                # salary_detail is a nested object: {minimum_salary, maximum_salary}
                salary_detail = item.get("salary_detail") or {}
                salary_str = None
                if salary_detail.get("minimum_salary") or salary_detail.get("maximum_salary"):
                    lo = salary_detail.get("minimum_salary", "")
                    hi = salary_detail.get("maximum_salary", "")
                    salary_str = f"{lo}-{hi} {salary_detail.get('currency', 'INR')}".strip("- ")
                jid = _upsert_job(
                    title=_pick(item, ["title", "jobTitle", "position"]),
                    company=_pick(item, ["company_name", "company", "companyName"]),
                    url=_pick(item, ["jd_url", "static_url", "url", "jobUrl", "link"]),
                    platform="naukri",
                    location=_pick(item, ["location", "jobLocation"]),
                    description=_pick(item, ["job_description", "description", "descriptionText"]),
                    salary_range=salary_str or _pick(item, ["salary", "salaryRange"]),
                    posted_at=_pick(item, ["created_date", "postedDate", "postedAt"]),
                )
                if jid:
                    job_ids.append(jid)
            logger.info(f"[naukri_tool] saved {len(job_ids)} jobs")
            return f"Naukri: saved {len(job_ids)} jobs. IDs: {','.join(job_ids)}"
        except Exception as e:
            logger.error(f"[naukri_tool] error: {e}")
            return f"Naukri search failed: {str(e)}"


# ── Google Jobs Tool (replaces Wellfound + Instahyre) ────────────────────────

class GoogleJobsTool(BaseTool):
    name: str = "Google Jobs Search"
    description: str = (
        "Search Google Jobs for live job listings in India matching a role/skill query. "
        "Covers jobs from all platforms (Naukri, LinkedIn, company sites, etc). "
        "Saves new jobs to the database and returns their IDs. "
        "Input: job title + key skills, e.g. 'Senior Data Engineer Spark India'."
    )
    args_schema: Type[BaseModel] = JobSearchInput

    def _run(self, search_query: str) -> str:
        try:
            client = _apify_client()
            run = client.actor(_GOOGLE_JOBS_ACTOR).call(
                run_input={
                    "query": search_query,
                    "domain": "co.in",
                    "location": "India",
                    "maxRows": 25,
                    "datePosted": "week",
                },
                timeout_secs=180,
            )
            items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
            if items:
                logger.info(f"[google_jobs_tool] {len(items)} items scraped. first item: {dict(list(items[0].items())[:10])}")
            job_ids = []
            for item in items:
                # links is a list of {url, source} dicts
                links = item.get("links") or []
                apply_url = links[0].get("url") if links else None
                jid = _upsert_job(
                    title=_pick(item, ["jobTitle", "title", "position"]),
                    company=_pick(item, ["companyName", "company", "employer"]),
                    url=apply_url or _pick(item, ["url", "link"]),
                    platform="google_jobs",
                    location=_pick(item, ["location", "jobLocation"]),
                    description=_pick(item, ["description", "descriptionText"]),
                    salary_range=_pick(item, ["salary", "salaryRange", "salaryInfo"]),
                    posted_at=_pick(item, ["publicationLapsTime", "postedAt", "datePosted"]),
                )
                if jid:
                    job_ids.append(jid)
            logger.info(f"[google_jobs_tool] saved {len(job_ids)} jobs")
            return f"Google Jobs: saved {len(job_ids)} jobs. IDs: {','.join(job_ids)}"
        except Exception as e:
            logger.error(f"[google_jobs_tool] error: {e}")
            return f"Google Jobs search failed: {str(e)}"


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
