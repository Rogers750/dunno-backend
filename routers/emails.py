import base64
import logging
import os
import resend
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from database.supabase_client import supabase_admin

logger = logging.getLogger(__name__)

router = APIRouter()

resend.api_key = os.getenv("RESEND_API_KEY", "")


class JobsDigestRequest(BaseModel):
    user_id: str


def _match_label(score: float) -> tuple[str, str]:
    if score >= 8.5:
        return "Very likely to get the call", "#2d7d46"
    if score >= 7.0:
        return "Likely to get the call", "#D4834A"
    if score >= 6.0:
        return "Moderate chance", "#D4834A"
    return "Lower match", "#6b4a28"


def _score_bar(label: str, value: float) -> str:
    pct = min(int(value * 10), 100)
    return f"""
      <tr>
        <td style="padding:3px 0;">
          <table width="100%" cellpadding="0" cellspacing="0" border="0">
            <tr>
              <td style="font-family:Arial,sans-serif;font-size:10px;color:#6b4a28;padding-bottom:2px;">{label}</td>
              <td align="right" style="font-family:Arial,sans-serif;font-size:10px;color:#6b4a28;padding-bottom:2px;">{value:.1f}</td>
            </tr>
            <tr>
              <td colspan="2">
                <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f0e4d4;border-radius:2px;height:3px;">
                  <tr>
                    <td width="{pct}%" style="background:linear-gradient(90deg,#D4834A,#8B4E1A);height:3px;border-radius:2px;font-size:0;">&nbsp;</td>
                    <td width="{100-pct}%" style="font-size:0;">&nbsp;</td>
                  </tr>
                </table>
              </td>
            </tr>
          </table>
        </td>
      </tr>"""


def _build_card(job_summary: dict) -> str:
    job = job_summary["job"]
    score = job_summary["match_score"]
    breakdown = job_summary.get("score_breakdown") or {}

    label, label_color = _match_label(score)

    role_s     = breakdown.get("role", 0)
    skills_s   = breakdown.get("skills", 0)
    edu_s      = breakdown.get("education", 0)
    exp_s      = breakdown.get("experience", 0)
    company_s  = breakdown.get("company_type", 0)

    location = job.get("location") or "India"
    company  = (job.get("company") or "").upper()
    title    = job.get("title") or ""

    return f"""
    <tr>
      <td style="padding:0 0 16px 0;">
        <table width="100%" cellpadding="0" cellspacing="0" border="0"
               style="background:#ffffff;border-radius:14px;border:1px solid #e8d9c8;">
          <tr>
            <td style="padding:18px 20px;">

              <!-- Company + Score badge -->
              <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom:8px;">
                <tr>
                  <td style="font-family:Arial,sans-serif;font-size:10px;font-weight:700;
                              letter-spacing:1px;color:#6b4a28;">{company}</td>
                  <td align="right">
                    <span style="background:linear-gradient(135deg,#D4834A,#8B4E1A);color:#ffffff;
                                 font-family:Arial,sans-serif;font-size:13px;font-weight:700;
                                 padding:4px 10px;border-radius:20px;white-space:nowrap;">
                      {score:.1f}<span style="font-size:9px;opacity:0.85;">/10</span>
                    </span>
                  </td>
                </tr>
              </table>

              <!-- Title -->
              <div style="font-family:Arial,sans-serif;font-size:15px;font-weight:700;
                           color:#1c0f00;line-height:1.35;margin-bottom:5px;">{title}</div>

              <!-- Match label -->
              <div style="font-family:Arial,sans-serif;font-size:11px;font-weight:600;
                           color:{label_color};margin-bottom:5px;">&#8226; {label}</div>

              <!-- Location -->
              <div style="font-family:Arial,sans-serif;font-size:11px;color:#6b4a28;
                           margin-bottom:14px;">&#128205; {location}</div>

              <!-- Score bars -->
              <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-bottom:14px;">
                {_score_bar("Role fit", role_s)}
                {_score_bar("Skills", skills_s)}
                {_score_bar("Education", edu_s)}
                {_score_bar("Experience", exp_s)}
                {_score_bar("Company type", company_s)}
              </table>

              <!-- Apply button -->
              <table cellpadding="0" cellspacing="0" border="0" style="margin-bottom:10px;">
                <tr>
                  <td style="background:linear-gradient(135deg,#D4834A,#8B4E1A);
                              border-radius:8px;">
                    <a href="https://dunnoai.com/dashboard"
                       style="display:inline-block;font-family:Arial,sans-serif;font-size:12px;
                              font-weight:700;color:#ffffff;text-decoration:none;
                              padding:9px 18px;">Apply Now &#8594;</a>
                  </td>
                </tr>
              </table>


            </td>
          </tr>
        </table>
      </td>
    </tr>"""


def _build_html(jobs: list[dict], count: int) -> str:
    cards = "\n".join(_build_card(j) for j in jobs)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{count} Jobs Matched for You - Dunno</title>
</head>
<body style="margin:0;padding:0;background:#f9f2e8;font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f9f2e8;">
    <tr>
      <td align="center" style="padding:32px 16px;">
        <table width="600" cellpadding="0" cellspacing="0" border="0" style="max-width:600px;width:100%;">

          <!-- Header -->
          <tr>
            <td style="background:#f9f2e8;border-radius:16px;border:1px solid #e8d9c8;
                        padding:28px 24px;text-align:center;margin-bottom:24px;">
              <img src="cid:dunnoai_logo" alt="Dunno" width="48" height="48"
                   style="display:block;margin:0 auto 8px;border-radius:10px;" />
              <div style="font-family:Arial,sans-serif;font-size:18px;font-weight:700;
                           color:#8B4E1A;letter-spacing:3px;text-transform:uppercase;
                           margin-bottom:10px;">DUNNO</div>
              <div style="font-family:Arial,sans-serif;font-size:22px;font-weight:700;
                           color:#1c0f00;margin-bottom:6px;">{count} jobs matched for you</div>
              <div style="font-family:Arial,sans-serif;font-size:13px;color:#6b4a28;">
                Based on your experience, skills, and salary expectations
              </div>
            </td>
          </tr>

          <tr><td style="height:20px;"></td></tr>

          <!-- Job cards -->
          <tr>
            <td>
              <table width="100%" cellpadding="0" cellspacing="0" border="0">
                {cards}
              </table>
            </td>
          </tr>

          <!-- Footer CTA -->
          <tr>
            <td style="background:linear-gradient(135deg,#D4834A,#8B4E1A);border-radius:16px;
                        padding:28px 24px;text-align:center;">
              <div style="font-family:Arial,sans-serif;font-size:18px;font-weight:700;
                           color:#ffffff;margin-bottom:6px;">Your resume &amp; cover letter is ready</div>
              <div style="font-family:Arial,sans-serif;font-size:13px;color:rgba(255,255,255,0.85);
                           margin-bottom:18px;">Dunno has already tailored your application for each of these jobs.</div>
              <a href="https://dunnoai.com/dashboard"
                 style="background:#ffffff;color:#8B4E1A;font-family:Arial,sans-serif;
                         font-size:13px;font-weight:700;padding:11px 30px;border-radius:8px;
                         text-decoration:none;display:inline-block;">
                View All Jobs on Dunno
              </a>
            </td>
          </tr>

          <tr><td style="height:20px;"></td></tr>

          <!-- Footer note -->
          <tr>
            <td style="text-align:center;font-family:Arial,sans-serif;font-size:11px;color:#b08060;">
              You're receiving this because you signed up for Dunno job alerts.<br>
              <a href="https://dunnoai.com/unsubscribe" style="color:#b08060;">Unsubscribe</a>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


# ── POST /emails/jobs-digest ──────────────────────────────────────────────────

@router.post("/jobs-digest")
async def send_jobs_digest(payload: JobsDigestRequest):
    if not resend.api_key:
        raise HTTPException(status_code=500, detail="RESEND_API_KEY not configured")

    profile = (
        supabase_admin.table("profiles")
        .select("email, username")
        .eq("id", payload.user_id)
        .limit(1)
        .execute()
    )
    if not profile.data:
        raise HTTPException(status_code=404, detail="User not found")

    email = profile.data[0].get("email")
    if not email:
        raise HTTPException(status_code=400, detail="User has no email address")

    # check last email sent — only include jobs created after that
    last_log = (
        supabase_admin.table("email_log")
        .select("sent_at, job_ids")
        .eq("user_id", payload.user_id)
        .eq("type", "jobs_digest")
        .order("sent_at", desc=True)
        .limit(1)
        .execute()
    )
    last_sent_at = last_log.data[0]["sent_at"] if last_log.data else None
    already_sent_ids = set(last_log.data[0].get("job_ids") or []) if last_log.data else set()

    query = (
        supabase_admin.table("user_matched_jobs")
        .select("id, job_id, match_score, score_breakdown, status, created_at")
        .eq("user_id", payload.user_id)
        .not_.in_("status", ["rejected"])
        .order("match_score", desc=True)
        .limit(6)
    )
    if last_sent_at:
        query = query.gt("created_at", last_sent_at)

    matches = query.execute()
    new_matches = [r for r in (matches.data or []) if r["id"] not in already_sent_ids]

    if not new_matches:
        logger.info(f"[emails/jobs-digest] no new jobs for user={payload.user_id}, skipping")
        return {"status": "skipped", "reason": "no new jobs since last email"}

    jobs = []
    for row in new_matches:
        job_row = supabase_admin.table("job_listings").select("*").eq("id", row["job_id"]).execute()
        if not job_row.data:
            continue
        job = job_row.data[0]
        jobs.append({
            "id": row["id"],
            "job": {
                "title": job["title"],
                "company": job["company"],
                "location": job.get("location"),
                "url": job["url"],
            },
            "match_score": row["match_score"],
            "score_breakdown": row.get("score_breakdown") or {},
        })

    if not jobs:
        return {"status": "skipped", "reason": "no new jobs since last email"}

    html = _build_html(jobs, len(jobs))

    logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "dunnoai.png")
    with open(logo_path, "rb") as f:
        logo_b64 = base64.b64encode(f.read()).decode()

    params: resend.Emails.SendParams = {
        "from": "Dunno <jobs@dunnoai.com>",
        "to": [email],
        "subject": f"{len(jobs)} new jobs matched for you on Dunno",
        "html": html,
        "attachments": [
            {
                "filename": "dunnoai.png",
                "content": logo_b64,
                "content_id": "dunnoai_logo",
            }
        ],
    }
    resend.Emails.send(params)

    supabase_admin.table("email_log").insert({
        "user_id": payload.user_id,
        "type": "jobs_digest",
        "jobs_count": len(jobs),
        "job_ids": [j["id"] for j in jobs],
    }).execute()

    logger.info(f"[emails/jobs-digest] sent to={email} user={payload.user_id} jobs={len(jobs)}")
    return {"status": "sent", "to": email, "jobs_count": len(jobs)}
