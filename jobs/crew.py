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


def _save_match(
    user_id: str,
    job_id: str,
    match_result: MatchResult,
    company_info: CompanyInfo,
    resume_json: dict,
    cover_letter: str,
    project_suggestions: ProjectSuggestions,
) -> None:
    supabase_admin.table("user_matched_jobs").insert({
        "user_id": user_id,
        "job_id": job_id,
        "match_score": match_result.match_score,
        "score_breakdown": match_result.score_breakdown.model_dump(),
        "resume_json": resume_json,
        "cover_letter": cover_letter,
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


def _run_resume_builder(gen_content: dict, job: dict) -> dict:
    from jobs.agents import build_resume_builder
    from jobs.tasks import build_resume_task

    agent = build_resume_builder(deepseek_llm)
    task = build_resume_task(agent, gen_content, job)
    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)
    result = crew.kickoff()

    raw = result.raw if hasattr(result, "raw") else str(result)
    raw = re.sub(r"^```(?:json)?\n?", "", raw.strip())
    raw = re.sub(r"\n?```$", "", raw.strip())
    try:
        return json.loads(raw)
    except Exception:
        logger.error("[crew] resume builder returned non-JSON")
        return {}


def _run_cover_letter_writer(gen_content: dict, job: dict, company_info: CompanyInfo) -> str:
    from jobs.agents import build_cover_letter_writer
    from jobs.tasks import build_cover_letter_task

    agent = build_cover_letter_writer(deepseek_llm)
    task = build_cover_letter_task(agent, gen_content, job, company_info.model_dump())
    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)
    result = crew.kickoff()
    return result.raw if hasattr(result, "raw") else str(result)


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
            "total_steps": 7,
            "current_agent": "Agent 1 — Job Searcher",
            "completed_agents": [],
            "jobs_found": 0,
            "jobs_processed": 0,
        }
        _update_progress(run_id, progress)

        job_ids = _run_job_search(target_roles, gen_content)

        progress["completed_agents"].append("Agent 1 — Job Searcher")
        progress["jobs_found"] = len(job_ids)
        _update_progress(run_id, progress)

        logger.info(f"[jobs_crew] agent1 found {len(job_ids)} jobs")

        if not job_ids:
            _fail_run(run_id, "No jobs found across all platforms")
            return

        # Filter already-matched
        existing = supabase_admin.table("user_matched_jobs").select("job_id").eq("user_id", user_id).execute()
        matched_ids = {r["job_id"] for r in (existing.data or [])}
        new_ids = [jid for jid in job_ids if jid not in matched_ids]

        # ── Agents 2–6 per job ────────────────────────────────────────────────
        processed = 0
        agent_names = [
            "Agent 2 — Profile Matcher",
            "Agent 3 — Company Researcher",
            "Agent 4 — Resume Builder",
            "Agent 5 — Cover Letter Writer",
            "Agent 6 — Project Advisor",
        ]

        for job_id in new_ids:
            if processed >= limit:
                break

            job = _fetch_job(job_id)
            if not job:
                continue

            logger.info(f"[jobs_crew] processing job={job_id} '{job['title']}' @ '{job['company']}'")

            try:
                # Agent 2
                progress["current_step"] = 2
                progress["current_agent"] = agent_names[0]
                _update_progress(run_id, progress)
                match_result = _run_matcher(gen_content, ctc, job)
                progress["completed_agents"].append(agent_names[0])

                # Agent 3
                progress["current_step"] = 3
                progress["current_agent"] = agent_names[1]
                _update_progress(run_id, progress)
                company_info = _run_company_researcher(job["company"])
                progress["completed_agents"].append(agent_names[1])

                # Agent 4
                progress["current_step"] = 4
                progress["current_agent"] = agent_names[2]
                _update_progress(run_id, progress)
                resume_json = _run_resume_builder(gen_content, job)
                progress["completed_agents"].append(agent_names[2])

                # Agent 5
                progress["current_step"] = 5
                progress["current_agent"] = agent_names[3]
                _update_progress(run_id, progress)
                cover_letter = _run_cover_letter_writer(gen_content, job, company_info)
                progress["completed_agents"].append(agent_names[3])

                # Agent 6
                progress["current_step"] = 6
                progress["current_agent"] = agent_names[4]
                _update_progress(run_id, progress)
                project_suggestions = _run_project_advisor(gen_content, job)
                progress["completed_agents"].append(agent_names[4])

                _save_match(
                    user_id=user_id,
                    job_id=job_id,
                    match_result=match_result,
                    company_info=company_info,
                    resume_json=resume_json,
                    cover_letter=cover_letter,
                    project_suggestions=project_suggestions,
                )

                processed += 1
                progress["jobs_processed"] = processed
                progress["current_step"] = 7
                progress["current_agent"] = f"Completed job {processed}/{min(limit, len(new_ids))}"
                # Reset completed_agents for next job
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
