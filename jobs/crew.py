import os
import re
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from crewai import LLM, Crew, Process

from database.supabase_client import supabase_admin
from jobs.schemas import MatchResult, CompanyInfo, ProjectSuggestions, ScoreBreakdown

logger = logging.getLogger(__name__)

# ── DeepSeek LLM — configured once, passed to all agents ─────────────────────

deepseek_llm = LLM(
    model="deepseek/deepseek-chat",
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)


# ── job_runs helpers ──────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_already_running(user_id: str) -> Optional[str]:
    """Return existing run id if a run is already in progress, else None."""
    result = (
        supabase_admin.table("job_runs")
        .select("id")
        .eq("user_id", user_id)
        .eq("status", "running")
        .execute()
    )
    return result.data[0]["id"] if result.data else None


def _create_run(user_id: str, trigger: str) -> str:
    result = supabase_admin.table("job_runs").insert({
        "user_id": user_id,
        "status": "running",
        "trigger": trigger,
        "started_at": _now(),
        "progress": {
            "current_step": 0,
            "total_steps": 7,
            "current_agent": "Agent 1 — Job Searcher",
            "completed_agents": [],
            "jobs_found": 0,
            "jobs_processed": 0,
        },
    }).execute()
    return result.data[0]["id"]


def _update_progress(run_id: str, progress: dict) -> None:
    supabase_admin.table("job_runs").update({"progress": progress}).eq("id", run_id).execute()


def _finish_run(run_id: str) -> None:
    supabase_admin.table("job_runs").update({
        "status": "done",
        "finished_at": _now(),
    }).eq("id", run_id).execute()


def _fail_run(run_id: str, error: str) -> None:
    supabase_admin.table("job_runs").update({
        "status": "failed",
        "finished_at": _now(),
        "error_message": error,
    }).eq("id", run_id).execute()


# ── Context loaders ───────────────────────────────────────────────────────────

def _load_user_context(user_id: str) -> Optional[dict]:
    profile = supabase_admin.table("profiles").select("id, username, email, ctc").eq("id", user_id).execute()
    portfolio = supabase_admin.table("portfolios").select("generated_content, target_roles").eq("user_id", user_id).eq("published", True).execute()

    if not profile.data or not portfolio.data:
        logger.warning(f"[crew] no profile or portfolio for user={user_id}")
        return None

    gen_content = portfolio.data[0].get("generated_content") or {}
    target_roles = portfolio.data[0].get("target_roles") or []

    if not gen_content:
        logger.warning(f"[crew] empty generated_content for user={user_id}")
        return None

    return {
        "profile": profile.data[0],
        "gen_content": gen_content,
        "target_roles": target_roles,
        "ctc": profile.data[0].get("ctc") or {},
    }


def _fetch_job(job_id: str) -> Optional[dict]:
    result = supabase_admin.table("job_listings").select("*").eq("id", job_id).execute()
    return result.data[0] if result.data else None


def _get_relevant_unmatched_from_db(
    target_roles: list[str],
    matched_ids: set,
    min_count: int = 15,
    days: int = 7,
) -> list[str]:
    """
    Check job_listings for recent, role-relevant, unmatched jobs.
    Returns IDs if >= min_count found, else empty list (triggers fresh scrape).
    Filters:
      - created within `days` days
      - is_live = True
      - title contains at least one target role keyword
      - not already in user_matched_jobs
    """
    from datetime import datetime, timezone, timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    recent = (
        supabase_admin.table("job_listings")
        .select("id, title")
        .eq("is_live", True)
        .gte("created_at", cutoff)
        .execute()
    )

    role_keywords = [r.lower().strip() for r in target_roles if r]
    # also split multi-word roles into individual keywords for broader matching
    # e.g. "Senior Data Engineer" → ["senior data engineer", "data engineer", "senior"]
    expanded = set()
    for role in role_keywords:
        expanded.add(role)
        parts = role.split()
        if len(parts) > 1:
            expanded.add(" ".join(parts[1:]))  # drop seniority prefix

    candidates = []
    for row in (recent.data or []):
        if row["id"] in matched_ids:
            continue
        title_lower = (row.get("title") or "").lower()
        if any(kw in title_lower for kw in expanded):
            candidates.append(row["id"])

    logger.info(
        f"[crew] DB pool check: {len(candidates)} relevant unmatched jobs "
        f"(need {min_count} to skip scrape)"
    )
    return candidates if len(candidates) >= min_count else []


def _save_match(
    user_id: str,
    job_id: str,
    match_result: MatchResult,
    company_info: CompanyInfo,
    project_suggestions: ProjectSuggestions,
) -> None:
    supabase_admin.table("user_matched_jobs").insert({
        "user_id": user_id,
        "job_id": job_id,
        "match_score": match_result.match_score,
        "score_breakdown": match_result.score_breakdown.model_dump(),
        "resume_json": None,
        "cover_letter": None,
        "project_suggestions": project_suggestions.model_dump(),
        "company_info": company_info.model_dump(),
        "status": "new",
    }).execute()


# ── Per-agent mini-crew runners ───────────────────────────────────────────────

def _run_job_search(target_roles: list, gen_content: dict) -> list[str]:
    from jobs.agents import build_job_searcher
    from jobs.tasks import build_job_search_task

    agent = build_job_searcher(deepseek_llm)
    task = build_job_search_task(agent, target_roles, gen_content)
    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)
    result = crew.kickoff()

    raw = result.raw if hasattr(result, "raw") else str(result)
    uuids = re.findall(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", raw)
    return list(dict.fromkeys(uuids))


def _run_matcher(gen_content: dict, ctc: dict, job: dict) -> MatchResult:
    from jobs.agents import build_profile_matcher
    from jobs.tasks import build_match_task

    agent = build_profile_matcher(deepseek_llm)
    task = build_match_task(agent, gen_content, ctc, job)
    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)
    result = crew.kickoff()

    if hasattr(result, "pydantic") and result.pydantic:
        return result.pydantic
    try:
        return MatchResult(**json.loads(result.raw))
    except Exception:
        return MatchResult(
            match_score=5.0,
            score_breakdown=ScoreBreakdown(role=5.0, skills=5.0, experience=5.0, education=5.0, company_type=5.0),
        )


def _run_company_researcher(company_name: str) -> CompanyInfo:
    from jobs.agents import build_company_researcher
    from jobs.tasks import build_company_research_task

    agent = build_company_researcher(deepseek_llm)
    task = build_company_research_task(agent, company_name)
    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)
    result = crew.kickoff()

    if hasattr(result, "pydantic") and result.pydantic:
        return result.pydantic
    try:
        return CompanyInfo(**json.loads(result.raw))
    except Exception:
        return CompanyInfo()



def _run_project_advisor(gen_content: dict, job: dict) -> ProjectSuggestions:
    from jobs.agents import build_project_advisor
    from jobs.tasks import build_project_advisor_task

    agent = build_project_advisor(deepseek_llm)
    task = build_project_advisor_task(agent, gen_content, job)
    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)
    result = crew.kickoff()

    if hasattr(result, "pydantic") and result.pydantic:
        return result.pydantic
    try:
        return ProjectSuggestions(**json.loads(result.raw))
    except Exception:
        return ProjectSuggestions(suggestions=[])


# ── Main orchestration ────────────────────────────────────────────────────────

def run_jobs_crew(user_id: str, limit: int = 7, trigger: str = "manual") -> None:
    logger.info(f"[jobs_crew] starting user={user_id} limit={limit} trigger={trigger}")

    # Guard: don't start if already running
    existing_run_id = _is_already_running(user_id)
    if existing_run_id:
        logger.info(f"[jobs_crew] run already in progress run_id={existing_run_id}, skipping")
        return

    run_id = _create_run(user_id, trigger)
    logger.info(f"[jobs_crew] created run_id={run_id}")

    try:
        ctx = _load_user_context(user_id)
        if not ctx:
            _fail_run(run_id, "No portfolio or profile found")
            return

        gen_content = ctx["gen_content"]
        target_roles = ctx["target_roles"]
        ctc = ctx["ctc"]

        if not target_roles:
            _fail_run(run_id, "No target_roles set on portfolio")
            return

        # ── Agent 1: Job Search ───────────────────────────────────────────────
        progress = {
            "current_step": 1,
            "total_steps": 5,
            "current_agent": "Agent 1 — Job Searcher",
            "completed_agents": [],
            "jobs_found": 0,
            "jobs_processed": 0,
        }
        _update_progress(run_id, progress)

        # Check already-matched jobs first (needed for both paths below)
        existing = supabase_admin.table("user_matched_jobs").select("job_id").eq("user_id", user_id).execute()
        matched_ids = {r["job_id"] for r in (existing.data or [])}

        # Try DB first — skip Apify if enough relevant recent jobs already exist
        db_ids = _get_relevant_unmatched_from_db(target_roles, matched_ids)
        if db_ids:
            new_ids = db_ids
            logger.info(f"[jobs_crew] skipping Apify — using {len(new_ids)} jobs from DB")
            progress["current_agent"] = "Agent 1 — Using cached jobs"
        else:
            logger.info(f"[jobs_crew] DB pool insufficient — running Apify scrapers")
            job_ids = _run_job_search(target_roles, gen_content)
            if not job_ids:
                _fail_run(run_id, "No jobs found across all platforms")
                return
            new_ids = [jid for jid in job_ids if jid not in matched_ids]

        progress["completed_agents"].append("Agent 1 — Job Searcher")
        progress["jobs_found"] = len(new_ids)
        _update_progress(run_id, progress)

        if not new_ids:
            _finish_run(run_id)
            logger.info(f"[jobs_crew] no new jobs to process for user={user_id}")
            return

        # ── Pass 1: Agent 2 scores ALL new jobs ──────────────────────────────
        # Score every new job first, then pick top `limit` by match_score.
        # This ensures we only build resumes/cover letters for the best matches.
        progress["current_step"] = 2
        progress["current_agent"] = f"Agent 2 — Scoring {len(new_ids)} jobs"
        progress["completed_agents"].append("Agent 1 — Job Searcher")
        _update_progress(run_id, progress)

        scored = []
        for job_id in new_ids:
            job = _fetch_job(job_id)
            if not job:
                continue
            try:
                match_result = _run_matcher(gen_content, ctc, job)
                scored.append((job_id, job, match_result))
                logger.info(f"[jobs_crew] scored job={job_id} '{job['title']}' score={match_result.match_score:.1f}")
            except Exception as e:
                logger.error(f"[jobs_crew] matcher failed job={job_id}: {e}", exc_info=True)

        # Sort descending by match_score, take top `limit`
        scored.sort(key=lambda x: x[2].match_score, reverse=True)
        top_jobs = scored[:limit]

        progress["completed_agents"].append("Agent 2 — Profile Matcher")
        progress["jobs_found"] = len(scored)
        _update_progress(run_id, progress)

        logger.info(f"[jobs_crew] scored {len(scored)} jobs, processing top {len(top_jobs)}")

        # ── Pass 2: Agents 3–4 on top `limit` jobs (company research + projects) ──
        processed = 0
        for job_id, job, match_result in top_jobs:
            logger.info(f"[jobs_crew] processing job={job_id} '{job['title']}' @ '{job['company']}' score={match_result.match_score:.1f}")

            try:
                # Agent 3
                progress["current_step"] = 3
                progress["current_agent"] = "Agent 3 — Company Researcher"
                _update_progress(run_id, progress)
                company_info = _run_company_researcher(job["company"])

                # Agent 4
                progress["current_step"] = 4
                progress["current_agent"] = "Agent 4 — Project Advisor"
                _update_progress(run_id, progress)
                project_suggestions = _run_project_advisor(gen_content, job)

                _save_match(
                    user_id=user_id,
                    job_id=job_id,
                    match_result=match_result,
                    company_info=company_info,
                    project_suggestions=project_suggestions,
                )

                processed += 1
                progress["jobs_processed"] = processed
                progress["current_step"] = 5
                progress["current_agent"] = f"Completed job {processed}/{len(top_jobs)}"
                progress["completed_agents"] = []
                _update_progress(run_id, progress)

                logger.info(f"[jobs_crew] saved match job={job_id} score={match_result.match_score:.1f}")

            except Exception as e:
                logger.error(f"[jobs_crew] failed job={job_id}: {e}", exc_info=True)
                continue

        _finish_run(run_id)
        logger.info(f"[jobs_crew] done user={user_id} processed={processed}")

    except Exception as e:
        logger.error(f"[jobs_crew] fatal error user={user_id}: {e}", exc_info=True)
        _fail_run(run_id, str(e))


# ── On-demand resume builder ──────────────────────────────────────────────────

def build_resume_for_match(user_id: str, match_id: str) -> dict:
    """
    Build + validate a tailored resume for a specific matched job.
    Called on demand when user clicks 'Build my resume'.
    Returns the resume JSON and persists it to user_matched_jobs.
    """
    from jobs.agents import build_resume_builder, build_resume_validator
    from jobs.tasks import build_resume_task, build_resume_validation_task

    ctx = _load_user_context(user_id)
    if not ctx:
        raise ValueError("No portfolio or profile found")

    match = supabase_admin.table("user_matched_jobs").select("job_id").eq("id", match_id).eq("user_id", user_id).execute()
    if not match.data:
        raise ValueError("Match not found")

    job = _fetch_job(match.data[0]["job_id"])
    if not job:
        raise ValueError("Job listing not found")

    gen_content = ctx["gen_content"]

    # Agent: Resume Builder
    builder = build_resume_builder(deepseek_llm)
    build_task = build_resume_task(builder, gen_content, job)
    build_result = Crew(agents=[builder], tasks=[build_task], process=Process.sequential, verbose=False).kickoff()

    raw = build_result.raw if hasattr(build_result, "raw") else str(build_result)
    raw = re.sub(r"^```(?:json)?\n?", "", raw.strip())
    raw = re.sub(r"\n?```$", "", raw.strip())
    try:
        resume_json = json.loads(raw)
    except Exception:
        logger.error("[build_resume] builder returned non-JSON, raw=%s", raw[:300])
        raise ValueError("Resume builder returned invalid JSON")

    # Agent: Validator — cross-checks against gen_content, fixes issues
    validator = build_resume_validator(deepseek_llm)
    validate_task = build_resume_validation_task(validator, gen_content, job, resume_json)
    validate_result = Crew(agents=[validator], tasks=[validate_task], process=Process.sequential, verbose=False).kickoff()

    val_raw = validate_result.raw if hasattr(validate_result, "raw") else str(validate_result)
    val_raw = re.sub(r"^```(?:json)?\n?", "", val_raw.strip())
    val_raw = re.sub(r"\n?```$", "", val_raw.strip())
    try:
        validated_json = json.loads(val_raw)
    except Exception:
        logger.warning("[build_resume] validator returned non-JSON, using builder output")
        validated_json = resume_json

    supabase_admin.table("user_matched_jobs").update({"resume_json": validated_json}).eq("id", match_id).execute()
    logger.info(f"[build_resume] saved resume match_id={match_id}")
    return validated_json


# ── On-demand cover letter writer ─────────────────────────────────────────────

def build_cover_for_match(user_id: str, match_id: str) -> str:
    """
    Build a tailored cover letter for a specific matched job.
    Called on demand when user clicks 'Build my cover letter'.
    Returns the cover letter text and persists it to user_matched_jobs.
    """
    from jobs.agents import build_cover_letter_writer
    from jobs.tasks import build_cover_letter_task

    ctx = _load_user_context(user_id)
    if not ctx:
        raise ValueError("No portfolio or profile found")

    match = supabase_admin.table("user_matched_jobs").select("job_id, company_info").eq("id", match_id).eq("user_id", user_id).execute()
    if not match.data:
        raise ValueError("Match not found")

    job = _fetch_job(match.data[0]["job_id"])
    if not job:
        raise ValueError("Job listing not found")

    company_info = CompanyInfo(**(match.data[0].get("company_info") or {}))

    agent = build_cover_letter_writer(deepseek_llm)
    task = build_cover_letter_task(agent, ctx["gen_content"], job, company_info.model_dump())
    result = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False).kickoff()
    cover_letter = result.raw if hasattr(result, "raw") else str(result)

    supabase_admin.table("user_matched_jobs").update({"cover_letter": cover_letter}).eq("id", match_id).execute()
    logger.info(f"[build_cover] saved cover letter match_id={match_id}")
    return cover_letter
