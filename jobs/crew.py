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
    profile = supabase_admin.table("profiles").select("id, username, email, ctc, job_preferences").eq("id", user_id).execute()
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
        "preferences": profile.data[0].get("job_preferences") or {},
    }


def _fetch_job(job_id: str) -> Optional[dict]:
    result = supabase_admin.table("job_listings").select("*").eq("id", job_id).execute()
    return result.data[0] if result.data else None


def _build_profile_text(gen_content: dict, target_roles: list[str]) -> str:
    """Build a text representation of the candidate profile for embedding."""
    skills_data = gen_content.get("skills", {})
    all_skills = []
    if isinstance(skills_data, dict):
        for cat in ["languages", "frameworks", "tools", "concepts"]:
            all_skills.extend(skills_data.get(cat, []))

    experience = gen_content.get("experience", [])
    exp_titles = [f"{e.get('role', '')} at {e.get('company', '')}" for e in experience[:5]]

    personal = gen_content.get("personal", {})
    bio = personal.get("bio") or personal.get("summary") or ""

    return (
        f"Target roles: {', '.join(target_roles)}\n"
        f"Skills: {', '.join(all_skills[:30])}\n"
        f"Experience: {', '.join(exp_titles)}\n"
        f"Bio: {bio[:500]}"
    )


def _generate_profile_embedding(gen_content: dict, target_roles: list[str]) -> Optional[list]:
    """Generate embedding for the user's profile. Used for vector similarity search."""
    try:
        from jobs.tools import _get_voyage_client
        text = _build_profile_text(gen_content, target_roles)
        client = _get_voyage_client()
        result = client.embed([text], model="voyage-3")
        return result.embeddings[0]
    except Exception as e:
        logger.warning(f"[crew] profile embedding failed: {e}")
        return None


def _get_relevant_unmatched_from_db(
    target_roles: list[str],
    matched_ids: set,
    preferences: dict,
    candidate_years: float,
    gen_content: dict,
    min_count: int = 15,
) -> list[str]:
    """
    Find relevant unmatched jobs using vector similarity search.
    Falls back to keyword filter if embeddings aren't available.
    Returns IDs if >= min_count found, else empty list (triggers fresh scrape).
    """
    exp_ceiling = candidate_years + 1.5
    preferred_locs = preferences.get("preferred_locations") or []
    exclude_ids = list(matched_ids)

    # ── Vector search (primary path) ─────────────────────────────────────────
    profile_embedding = _generate_profile_embedding(gen_content, target_roles)
    if profile_embedding:
        try:
            result = supabase_admin.rpc("match_jobs", {
                "query_embedding": profile_embedding,
                "exclude_ids": exclude_ids,
                "exp_ceiling": exp_ceiling,
                "preferred_locs": preferred_locs,
                "match_count": 50,
            }).execute()

            candidates = [row["id"] for row in (result.data or [])]
            logger.info(
                f"[crew] vector search: {len(candidates)} candidates "
                f"(candidate_years={candidate_years}, exp_ceiling={exp_ceiling})"
            )
            return candidates if len(candidates) >= min_count else []
        except Exception as e:
            logger.warning(f"[crew] vector search failed, falling back to keyword: {e}")

    # ── Keyword fallback (for jobs with no embedding yet) ────────────────────
    from datetime import datetime, timezone, timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

    recent = (
        supabase_admin.table("job_listings")
        .select("id, title, location")
        .eq("is_live", True)
        .gte("created_at", cutoff)
        .or_(f"min_experience.is.null,min_experience.lte.{exp_ceiling}")
        .execute()
    )

    _GENERIC = {"engineer", "developer", "manager", "analyst", "lead", "architect", "consultant"}
    role_keywords = [r.lower().strip() for r in target_roles if r]
    expanded = set()
    for role in role_keywords:
        expanded.add(role)
        parts = role.split()
        if len(parts) > 1:
            tail = " ".join(parts[1:])
            if len(tail.split()) > 1 or tail not in _GENERIC:
                expanded.add(tail)

    preferred_locations = [l.lower() for l in preferred_locs]
    candidates = []
    for row in (recent.data or []):
        if row["id"] in matched_ids:
            continue
        title_lower = (row.get("title") or "").lower()
        if not any(kw in title_lower for kw in expanded):
            continue
        if preferred_locations:
            loc = (row.get("location") or "").lower()
            remote_ok = "remote" in preferred_locations
            if not any(pl in loc for pl in preferred_locations) and not (remote_ok and "remote" in loc):
                continue
        candidates.append(row["id"])

    logger.info(f"[crew] keyword fallback: {len(candidates)} candidates")
    return candidates if len(candidates) >= min_count else []


def _save_match(user_id: str, job_id: str, match_result: MatchResult) -> None:
    supabase_admin.table("user_matched_jobs").insert({
        "user_id": user_id,
        "job_id": job_id,
        "match_score": match_result.match_score,
        "score_breakdown": match_result.score_breakdown.model_dump(),
        "resume_json": None,
        "cover_letter": None,
        "project_suggestions": None,
        "company_info": None,
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


def _calc_match_score(breakdown: ScoreBreakdown) -> float:
    """Calculate match_score from breakdown in Python — never trust LLM arithmetic."""
    score = (
        breakdown.role        * 0.30 +
        breakdown.skills      * 0.25 +
        breakdown.experience  * 0.25 +
        breakdown.education   * 0.10 +
        breakdown.company_type * 0.10
    )
    if breakdown.compensation is not None:
        score = score * 0.90 + breakdown.compensation * 0.10
    return round(score, 1)


def _run_matcher(gen_content: dict, ctc: dict, job: dict, preferences: dict | None = None, target_roles: list | None = None) -> MatchResult:
    from jobs.agents import build_profile_matcher
    from jobs.tasks import build_match_task
    from jobs.scoring import extract_candidate_years, extract_required_years, calc_experience_score

    agent = build_profile_matcher(deepseek_llm)
    task = build_match_task(agent, gen_content, ctc, job, preferences, target_roles)
    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)
    result = crew.kickoff()

    if hasattr(result, "pydantic") and result.pydantic:
        match = result.pydantic
    else:
        try:
            match = MatchResult(**json.loads(result.raw))
        except Exception:
            match = MatchResult(
                match_score=5.0,
                score_breakdown=ScoreBreakdown(role=5.0, skills=5.0, experience=5.0, education=5.0, company_type=5.0),
            )

    # ── Enforce experience anchor — override if DeepSeek drifted ─────────────
    description = job.get("description") or ""
    candidate_years = extract_candidate_years(gen_content)
    min_req, max_req = extract_required_years(description)
    experience_score = calc_experience_score(candidate_years, min_req, max_req)

    logger.info(
        f"[matcher] experience anchor: candidate={candidate_years}yr, "
        f"jd_required={min_req}-{max_req}yr, anchor={experience_score}, "
        f"deepseek={match.score_breakdown.experience}"
    )

    if experience_score is not None and match.score_breakdown.experience != experience_score:
        logger.info(
            f"[matcher] overriding experience score: "
            f"DeepSeek={match.score_breakdown.experience} → enforced={experience_score}"
        )
        match.score_breakdown.experience = experience_score
    elif experience_score is None:
        logger.warning(
            f"[matcher] could not parse required years from JD — using DeepSeek score {match.score_breakdown.experience}"
        )

    # ── Recalculate match_score in Python — never trust LLM arithmetic ───────
    match.match_score = _calc_match_score(match.score_breakdown)
    logger.info(f"[matcher] final score={match.match_score} breakdown={match.score_breakdown}")

    return match


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


def _norm_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip()).lower()


def _build_source_role_lookup(gen_content: dict) -> tuple[dict, dict]:
    """
    Build lookups from source portfolio experience so generated resumes can keep
    the user's original role naming instead of letting the LLM rephrase titles.
    """
    by_company_and_dates: dict[tuple[str, str, str], str] = {}
    by_company: dict[str, list[str]] = {}

    for exp in gen_content.get("experience", []) or []:
        if not isinstance(exp, dict):
            continue
        company = _norm_text(exp.get("company", ""))
        role = (exp.get("role") or "").strip()
        if not company or not role:
            continue

        start = _norm_text(exp.get("startDate") or exp.get("sortDate") or "")
        end = _norm_text(exp.get("endDate") or exp.get("endSortDate") or "")
        if start or end:
            by_company_and_dates[(company, start, end)] = role
        by_company.setdefault(company, []).append(role)

    return by_company_and_dates, by_company


def _enforce_source_role_titles(resume_json: dict, gen_content: dict) -> dict:
    """
    Restore experience.role values from the source portfolio wherever possible.
    This keeps naming monotonous and prevents the LLM from changing titles like
    "Backend Engineer II" into arbitrary variants unless the source actually
    contains a different role.
    """
    experience = resume_json.get("experience")
    if not isinstance(experience, list):
        return resume_json

    by_company_and_dates, by_company = _build_source_role_lookup(gen_content)

    for exp in experience:
        if not isinstance(exp, dict):
            continue

        company = _norm_text(exp.get("company", ""))
        start = _norm_text(exp.get("startDate") or exp.get("sortDate") or "")
        end = _norm_text(exp.get("endDate") or exp.get("endSortDate") or "")

        source_role = by_company_and_dates.get((company, start, end))
        if source_role:
            exp["role"] = source_role
            continue

        roles_for_company = by_company.get(company) or []
        if len(set(roles_for_company)) == 1:
            exp["role"] = roles_for_company[0]

    return resume_json


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
        preferences = ctx["preferences"]
        from jobs.scoring import extract_candidate_years
        candidate_years = extract_candidate_years(gen_content)
        db_ids = _get_relevant_unmatched_from_db(target_roles, matched_ids, preferences, candidate_years, gen_content)
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
                match_result = _run_matcher(gen_content, ctc, job, preferences, target_roles)
                scored.append((job_id, job, match_result))
                logger.info(f"[jobs_crew] scored job={job_id} '{job['title']}' score={match_result.match_score:.1f}")
            except Exception as e:
                logger.error(f"[jobs_crew] matcher failed job={job_id}: {e}", exc_info=True)

        # Sort by match_score — vector search + LLM scoring is enough, no re-ranking needed
        scored.sort(key=lambda x: x[2].match_score, reverse=True)

        # Drop anything below 6.0 — not worth showing to the user
        MIN_SCORE = 6.0
        qualified = [(jid, job, mr) for jid, job, mr in scored if mr.match_score >= MIN_SCORE]
        top_jobs = qualified[:limit]

        progress["completed_agents"].append("Agent 2 — Profile Matcher")
        progress["jobs_found"] = len(scored)
        _update_progress(run_id, progress)

        logger.info(
            f"[jobs_crew] scored {len(scored)} jobs, "
            f"{len(qualified)} above {MIN_SCORE}, saving top {len(top_jobs)}"
        )

        # ── Save top matches — company/projects fetched on-demand by user ────
        processed = 0
        for job_id, job, match_result in top_jobs:
            try:
                _save_match(user_id=user_id, job_id=job_id, match_result=match_result)
                processed += 1
                progress["jobs_processed"] = processed
                progress["current_agent"] = f"Saved {processed}/{len(top_jobs)} matches"
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

    validated_json = _enforce_source_role_titles(validated_json, gen_content)

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


# ── On-demand company researcher ──────────────────────────────────────────────

def build_company_for_match(user_id: str, match_id: str) -> dict:
    """Fetch Glassdoor data for a matched job's company. Called on demand."""
    match = supabase_admin.table("user_matched_jobs").select("job_id").eq("id", match_id).eq("user_id", user_id).execute()
    if not match.data:
        raise ValueError("Match not found")

    job = _fetch_job(match.data[0]["job_id"])
    if not job:
        raise ValueError("Job listing not found")

    company_info = _run_company_researcher(job["company"])
    supabase_admin.table("user_matched_jobs").update({"company_info": company_info.model_dump()}).eq("id", match_id).execute()
    logger.info(f"[build_company] saved company info match_id={match_id}")
    return company_info.model_dump()


# ── On-demand project advisor ─────────────────────────────────────────────────

def build_projects_for_match(user_id: str, match_id: str) -> dict:
    """Generate project suggestions for a matched job. Called on demand."""
    ctx = _load_user_context(user_id)
    if not ctx:
        raise ValueError("No portfolio or profile found")

    match = supabase_admin.table("user_matched_jobs").select("job_id").eq("id", match_id).eq("user_id", user_id).execute()
    if not match.data:
        raise ValueError("Match not found")

    job = _fetch_job(match.data[0]["job_id"])
    if not job:
        raise ValueError("Job listing not found")

    suggestions = _run_project_advisor(ctx["gen_content"], job)
    supabase_admin.table("user_matched_jobs").update({"project_suggestions": suggestions.model_dump()}).eq("id", match_id).execute()
    logger.info(f"[build_projects] saved project suggestions match_id={match_id}")
    return suggestions.model_dump()


def build_general_resume_and_cover(user_id: str) -> dict:
    """
    Build an all-purpose resume JSON and reusable cover letter from the user's
    published portfolio. Unlike the matched-job flow, this is not tied to a
    specific company or job description and returns the result directly.
    """
    from jobs.agents import build_resume_builder, build_resume_validator, build_cover_letter_writer
    from jobs.tasks import (
        build_general_resume_task,
        build_general_resume_validation_task,
        build_general_cover_letter_task,
    )

    ctx = _load_user_context(user_id)
    if not ctx:
        raise ValueError("No published portfolio or profile found")

    gen_content = ctx["gen_content"]
    target_roles = ctx["target_roles"] or []
    portfolio_row = (
        supabase_admin.table("portfolios")
        .select("id")
        .eq("user_id", user_id)
        .eq("published", True)
        .limit(1)
        .execute()
    )
    if not portfolio_row.data:
        raise ValueError("No published portfolio found")
    portfolio_id = portfolio_row.data[0]["id"]

    builder = build_resume_builder(deepseek_llm)
    build_task = build_general_resume_task(builder, gen_content, target_roles)
    build_result = Crew(
        agents=[builder],
        tasks=[build_task],
        process=Process.sequential,
        verbose=False,
    ).kickoff()

    raw = build_result.raw if hasattr(build_result, "raw") else str(build_result)
    raw = re.sub(r"^```(?:json)?\n?", "", raw.strip())
    raw = re.sub(r"\n?```$", "", raw.strip())
    try:
        resume_json = json.loads(raw)
    except Exception:
        logger.error("[build_general_resume_and_cover] builder returned non-JSON, raw=%s", raw[:300])
        raise ValueError("Resume builder returned invalid JSON")

    validator = build_resume_validator(deepseek_llm)
    validate_task = build_general_resume_validation_task(
        validator, gen_content, target_roles, resume_json
    )
    validate_result = Crew(
        agents=[validator],
        tasks=[validate_task],
        process=Process.sequential,
        verbose=False,
    ).kickoff()

    val_raw = validate_result.raw if hasattr(validate_result, "raw") else str(validate_result)
    val_raw = re.sub(r"^```(?:json)?\n?", "", val_raw.strip())
    val_raw = re.sub(r"\n?```$", "", val_raw.strip())
    try:
        validated_json = json.loads(val_raw)
    except Exception:
        logger.warning("[build_general_resume_and_cover] validator returned non-JSON, using builder output")
        validated_json = resume_json

    validated_json = _enforce_source_role_titles(validated_json, gen_content)

    cover_agent = build_cover_letter_writer(deepseek_llm)
    cover_task = build_general_cover_letter_task(cover_agent, gen_content, target_roles)
    cover_result = Crew(
        agents=[cover_agent],
        tasks=[cover_task],
        process=Process.sequential,
        verbose=False,
    ).kickoff()
    cover_letter = cover_result.raw if hasattr(cover_result, "raw") else str(cover_result)

    payload = {
        "general_resume_json": validated_json,
        "general_cover_letter": cover_letter,
    }
    supabase_admin.table("portfolios").update(payload).eq("id", portfolio_id).execute()

    return {
        "resume_json": validated_json,
        "cover_letter": cover_letter,
    }
