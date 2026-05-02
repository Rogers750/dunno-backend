import logging
from fastapi import APIRouter, BackgroundTasks, HTTPException, Depends
from fastapi.responses import Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from database.supabase_client import supabase, supabase_admin
from jobs.schemas import CTCUpdate

logger = logging.getLogger(__name__)

# Two routers — registered with different prefixes in main.py
jobs_router = APIRouter()
profile_router = APIRouter()

security = HTTPBearer(auto_error=False)


# ── Auth helper ───────────────────────────────────────────────────────────────

def _get_user(credentials: HTTPAuthorizationCredentials):
    if not credentials:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    try:
        result = supabase.auth.get_user(credentials.credentials)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    if not result.user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return result.user


# ── Response builder ──────────────────────────────────────────────────────────

def _build_summary(row: dict, job: dict) -> dict:
    breakdown_raw = row.get("score_breakdown") or {}
    company_raw = row.get("company_info") or {}
    return {
        "id": row["id"],
        "job": {
            "id": job["id"],
            "title": job["title"],
            "company": job["company"],
            "location": job.get("location"),
            "url": job["url"],
            "platform": job["platform"],
            "description": job.get("description"),
            "salary_range": job.get("salary_range"),
            "posted_at": job.get("posted_at") and str(job["posted_at"]),
        },
        "match_score": row["match_score"],
        "score_breakdown": breakdown_raw or None,
        "company_info": company_raw or None,
        "status": row["status"],
    }


# ── GET /jobs/status ─────────────────────────────────────────────────────────

@jobs_router.get("/status")
async def get_job_status(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Latest job run status for the current user. Poll every 5s while running."""
    user = _get_user(credentials)

    row = (
        supabase_admin.table("job_runs")
        .select("*")
        .eq("user_id", user.id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )

    if not row.data:
        return {"status": "idle"}

    r = row.data[0]
    return {
        "status": r["status"],
        "progress": r.get("progress"),
        "trigger": r.get("trigger"),
        "started_at": r.get("started_at"),
        "finished_at": r.get("finished_at"),
        "error_message": r.get("error_message"),
    }


# ── POST /jobs/run ────────────────────────────────────────────────────────────

@jobs_router.post("/run")
async def run_jobs(
    background_tasks: BackgroundTasks,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Start job matching for the current user.
    Returns 202 immediately. Poll GET /jobs/status every 5s for progress.
    Returns 409 if a run is already in progress.
    """
    user = _get_user(credentials)

    from jobs.crew import run_jobs_crew, _is_already_running
    if _is_already_running(user.id):
        return {"status": "running", "message": "A run is already in progress. Poll GET /jobs/status for updates."}

    background_tasks.add_task(run_jobs_crew, user_id=user.id, limit=7, trigger="manual")
    logger.info(f"[jobs/run] queued for user={user.id}")
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=202, content={"status": "running", "message": "Job matching started. Poll GET /jobs/status for progress."})


# ── GET /jobs ─────────────────────────────────────────────────────────────────

@jobs_router.get("")
async def list_jobs(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Top 10 unapplied matched jobs for the current user, sorted by match_score."""
    user = _get_user(credentials)

    matches = (
        supabase_admin.table("user_matched_jobs")
        .select("id, job_id, match_score, score_breakdown, company_info, status")
        .eq("user_id", user.id)
        .neq("status", "applied")
        .order("match_score", desc=True)
        .limit(10)
        .execute()
    )

    results = []
    for row in matches.data or []:
        job_row = supabase_admin.table("job_listings").select("*").eq("id", row["job_id"]).execute()
        if not job_row.data:
            continue
        results.append(_build_summary(row, job_row.data[0]))

    return results


# ── GET /jobs/:id ─────────────────────────────────────────────────────────────

@jobs_router.get("/{match_id}")
async def get_job(
    match_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Full detail for one matched job including resume, cover letter, projects."""
    user = _get_user(credentials)

    row = (
        supabase_admin.table("user_matched_jobs")
        .select("*")
        .eq("id", match_id)
        .eq("user_id", user.id)
        .execute()
    )
    if not row.data:
        raise HTTPException(status_code=404, detail="Match not found")

    match = row.data[0]
    job_row = supabase_admin.table("job_listings").select("*").eq("id", match["job_id"]).execute()
    if not job_row.data:
        raise HTTPException(status_code=404, detail="Job listing not found")

    summary = _build_summary(match, job_row.data[0])
    suggestions_raw = match.get("project_suggestions") or {}
    project_list = suggestions_raw.get("suggestions", []) if isinstance(suggestions_raw, dict) else []

    return {
        **summary,
        "resume_json": match.get("resume_json"),
        "cover_letter": match.get("cover_letter"),
        "project_suggestions": project_list,
    }


# ── POST /jobs/:id/apply ──────────────────────────────────────────────────────

@jobs_router.post("/{match_id}/apply")
async def apply_job(
    match_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Mark a matched job as applied. Removes it from the top-10 list."""
    user = _get_user(credentials)

    row = (
        supabase_admin.table("user_matched_jobs")
        .select("id")
        .eq("id", match_id)
        .eq("user_id", user.id)
        .execute()
    )
    if not row.data:
        raise HTTPException(status_code=404, detail="Match not found")

    updated = (
        supabase_admin.table("user_matched_jobs")
        .update({"status": "applied"})
        .eq("id", match_id)
        .execute()
    )
    return updated.data[0] if updated.data else {"id": match_id, "status": "applied"}


# ── GET /jobs/:id/resume ──────────────────────────────────────────────────────

@jobs_router.get("/{match_id}/resume")
async def get_resume(
    match_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Return the tailored resume JSON for a matched job."""
    user = _get_user(credentials)

    row = (
        supabase_admin.table("user_matched_jobs")
        .select("resume_json")
        .eq("id", match_id)
        .eq("user_id", user.id)
        .execute()
    )
    if not row.data:
        raise HTTPException(status_code=404, detail="Match not found")

    return {"resume_json": row.data[0].get("resume_json") or {}}


# ── GET /jobs/:id/resume/pdf — Agent 7 ───────────────────────────────────────

@jobs_router.get("/{match_id}/resume/pdf")
async def get_resume_pdf(
    match_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Render the tailored resume to PDF (Agent 7).
    If pdf_path already exists, serve from Supabase Storage directly.
    Otherwise render via pyppeteer, upload, then serve.
    """
    user = _get_user(credentials)

    row = (
        supabase_admin.table("user_matched_jobs")
        .select("id, job_id, resume_json, pdf_path")
        .eq("id", match_id)
        .eq("user_id", user.id)
        .execute()
    )
    if not row.data:
        raise HTTPException(status_code=404, detail="Match not found")

    match = row.data[0]
    resume_json = match.get("resume_json")
    if not resume_json:
        raise HTTPException(status_code=400, detail="No resume JSON found. Generate portfolio first.")

    # Serve cached PDF if already rendered
    if match.get("pdf_path"):
        from jobs.storage import download_resume_pdf
        try:
            pdf_bytes = download_resume_pdf(match["pdf_path"])
            return Response(
                content=pdf_bytes,
                media_type="application/pdf",
                headers={"Content-Disposition": "attachment; filename=resume.pdf"},
            )
        except Exception:
            pass  # fall through to re-render

    # Agent 7 — render HTML → PDF
    from crewai import Crew, Process
    from jobs.agents import build_pdf_renderer
    from jobs.tasks import build_pdf_render_task
    from jobs.storage import render_resume_pdf_sync, upload_resume_pdf

    agent = build_pdf_renderer(
        __import__("jobs.crew", fromlist=["deepseek_llm"]).deepseek_llm
    )
    task = build_pdf_render_task(agent, resume_json)
    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)
    result = crew.kickoff()
    html = result.raw if hasattr(result, "raw") else str(result)

    pdf_bytes = render_resume_pdf_sync(html)
    pdf_path = upload_resume_pdf(user_id=user.id, job_id=match["job_id"], pdf_bytes=pdf_bytes)

    supabase_admin.table("user_matched_jobs").update({"pdf_path": pdf_path}).eq("id", match_id).execute()

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=resume.pdf"},
    )


# ── GET /jobs/:id/cover ───────────────────────────────────────────────────────

@jobs_router.get("/{match_id}/cover")
async def get_cover_letter(
    match_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    user = _get_user(credentials)

    row = (
        supabase_admin.table("user_matched_jobs")
        .select("cover_letter")
        .eq("id", match_id)
        .eq("user_id", user.id)
        .execute()
    )
    if not row.data:
        raise HTTPException(status_code=404, detail="Match not found")

    return {"cover_letter": row.data[0].get("cover_letter") or ""}


# ── GET /jobs/:id/projects ────────────────────────────────────────────────────

@jobs_router.get("/{match_id}/projects")
async def get_project_suggestions(
    match_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    user = _get_user(credentials)

    row = (
        supabase_admin.table("user_matched_jobs")
        .select("project_suggestions")
        .eq("id", match_id)
        .eq("user_id", user.id)
        .execute()
    )
    if not row.data:
        raise HTTPException(status_code=404, detail="Match not found")

    raw = row.data[0].get("project_suggestions") or {}
    suggestions = raw.get("suggestions", []) if isinstance(raw, dict) else []
    return {"project_suggestions": suggestions}


# ── GET /jobs/:id/company ─────────────────────────────────────────────────────

@jobs_router.get("/{match_id}/company")
async def get_company_info(
    match_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    user = _get_user(credentials)

    row = (
        supabase_admin.table("user_matched_jobs")
        .select("company_info")
        .eq("id", match_id)
        .eq("user_id", user.id)
        .execute()
    )
    if not row.data:
        raise HTTPException(status_code=404, detail="Match not found")

    return {"company_info": row.data[0].get("company_info") or {}}


# ── PATCH /profile/ctc ────────────────────────────────────────────────────────

@profile_router.patch("/ctc")
async def update_ctc(
    payload: CTCUpdate,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Update current and expected CTC for the authenticated user."""
    user = _get_user(credentials)

    result = (
        supabase_admin.table("profiles")
        .update({
            "ctc": {
                "current_base_in_lakhs": payload.current_base_in_lakhs,
                "expected_base_in_lakhs": payload.expected_base_in_lakhs,
            }
        })
        .eq("id", user.id)
        .execute()
    )

    if not result.data:
        raise HTTPException(status_code=404, detail="Profile not found")

    logger.info(
        f"[profile/ctc] user={user.id} "
        f"current={payload.current_base_in_lakhs} expected={payload.expected_base_in_lakhs}"
    )
    return result.data[0]
