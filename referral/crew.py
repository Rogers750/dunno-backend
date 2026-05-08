import os
import re
import json
import logging
from typing import Optional

from apify_client import ApifyClient
from crewai import LLM, Crew, Agent, Task, Process

logger = logging.getLogger(__name__)

_LINKEDIN_PROFILE_ACTOR = os.getenv(
    "APIFY_LINKEDIN_PROFILE_ACTOR", "curious_coder/linkedin-profile-scraper"
)

deepseek_llm = LLM(
    model="deepseek/deepseek-chat",
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)


# ── Apify profile scraper ─────────────────────────────────────────────────────

def _scrape_linkedin_profile(url: str) -> Optional[dict]:
    token = os.getenv("APIFY_TOKEN")
    if not token:
        raise ValueError("APIFY_TOKEN is not set")

    client = ApifyClient(token)
    try:
        run = client.actor(_LINKEDIN_PROFILE_ACTOR).call(
            run_input={"profileUrls": [url]},
            timeout_secs=120,
        )
        items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
        if not items:
            return None
        return items[0]
    except Exception as e:
        logger.error(f"[referral] profile scrape failed: {e}")
        return None


# ── Connection finder ─────────────────────────────────────────────────────────

def _find_connections(profile: dict, gen_content: dict) -> list[str]:
    """
    Compare scraped LinkedIn profile with user's portfolio.
    Returns list of connection strings e.g. ["Same college: NIT Kurukshetra", "Both worked at Dezerv"]
    """
    connections = []

    # Normalise helper
    def norm(s: str) -> str:
        return re.sub(r"\s+", " ", (s or "").strip().lower())

    # ── Education overlap ─────────────────────────────────────────────────────
    user_schools = set()
    for edu in gen_content.get("education", []) or []:
        inst = norm(edu.get("institution") or edu.get("school") or "")
        if inst:
            user_schools.add(inst)

    profile_edu = profile.get("education") or profile.get("educations") or []
    for edu in profile_edu:
        school = norm(
            edu.get("schoolName") or edu.get("school") or edu.get("institution") or ""
        )
        if school:
            for user_school in user_schools:
                # substring match handles "NIT Kurukshetra" vs "National Institute of Technology, Kurukshetra"
                if user_school in school or school in user_school:
                    connections.append(f"Same college: {edu.get('schoolName') or edu.get('school') or school.title()}")
                    break

    # ── Company overlap ───────────────────────────────────────────────────────
    user_companies = set()
    for exp in gen_content.get("experience", []) or []:
        company = norm(exp.get("company") or "")
        if company:
            user_companies.add(company)

    profile_exp = profile.get("experience") or profile.get("positions") or []
    for exp in profile_exp:
        company = norm(
            exp.get("companyName") or exp.get("company") or exp.get("title") or ""
        )
        if company:
            for user_company in user_companies:
                if user_company in company or company in user_company:
                    connections.append(f"Both worked at: {exp.get('companyName') or exp.get('company') or company.title()}")
                    break

    return connections


def _check_company_mismatch(profile: dict, target_company: str) -> bool:
    """Returns True if the person clearly does NOT work at target_company."""
    target_norm = re.sub(r"\s+", " ", target_company.strip().lower())

    # Current position
    positions = profile.get("experience") or profile.get("positions") or []
    for pos in positions:
        is_current = (
            pos.get("endDate") is None
            or pos.get("endDate") == ""
            or "present" in str(pos.get("endDate") or "").lower()
        )
        if not is_current:
            continue
        company = re.sub(r"\s+", " ", (
            pos.get("companyName") or pos.get("company") or ""
        ).strip().lower())
        if target_norm in company or company in target_norm:
            return False  # found a match — no mismatch

    # headline / summary sometimes contains current company
    headline = (profile.get("headline") or "").lower()
    if target_norm in headline:
        return False

    # If we have positions but none matched, flag it
    if positions:
        return True

    # No positions at all — can't tell, don't warn
    return False


# ── Referral message agent ────────────────────────────────────────────────────

def _build_referral_prompt(
    profile: dict,
    gen_content: dict,
    company: str,
    role: str,
    connections: list[str],
) -> str:
    personal = gen_content.get("personal", {})
    user_name = personal.get("name", "")
    user_title = personal.get("title", "")
    user_bio = personal.get("bio", "")

    user_exp_summary = []
    for exp in (gen_content.get("experience", []) or [])[:3]:
        user_exp_summary.append(f"{exp.get('role')} at {exp.get('company')}")

    profile_name = profile.get("fullName") or profile.get("name") or "this person"
    profile_headline = profile.get("headline") or ""
    profile_summary = profile.get("summary") or profile.get("about") or ""

    profile_exp_lines = []
    for exp in (profile.get("experience") or profile.get("positions") or [])[:3]:
        profile_exp_lines.append(
            f"{exp.get('title') or exp.get('role')} at {exp.get('companyName') or exp.get('company')}"
        )

    profile_edu_lines = []
    for edu in (profile.get("education") or profile.get("educations") or [])[:2]:
        profile_edu_lines.append(
            edu.get("schoolName") or edu.get("school") or edu.get("institution") or ""
        )

    connections_str = "\n".join(f"- {c}" for c in connections) if connections else "None found"

    return f"""
Write a referral request message from {user_name} to {profile_name} asking for a referral at {company} for the role of {role}.

## About the sender ({user_name})
Title: {user_title}
Background: {user_bio}
Recent experience: {", ".join(user_exp_summary)}

## About the recipient ({profile_name})
Headline: {profile_headline}
Summary: {profile_summary[:500]}
Their experience: {", ".join(profile_exp_lines)}
Their education: {", ".join(profile_edu_lines)}

## Shared connections between them
{connections_str}

## Writing rules
- Address {profile_name} by first name
- Open with the shared connection(s) if any — that's the strongest hook
- If no shared connections, open with something specific about their work or background that you genuinely respect
- Be direct: mention you're applying for "{role}" at {company} and would appreciate a referral or an internal intro
- Keep it short — 3-4 short paragraphs max, this is a LinkedIn DM not an email
- Sound like a real person typing this, not a template — no "I hope this message finds you well", no "I am reaching out to", no corporate filler
- Slight informality is fine. Confident but not pushy
- End with a low-pressure ask: "happy to share my resume if helpful" or "totally understand if it's not possible"
- Do NOT use buzzwords, "passionate", "excited to", "synergy", or any Steve Jobs language
- Output plain text only. No subject line. No Dear/To. Just the message body.
"""


def generate_referral_message(
    linkedin_url: str,
    company: str,
    role: str,
    gen_content: dict,
) -> dict:
    """
    Scrape the LinkedIn profile, find connections with user, generate referral message.
    Returns dict with: message, warning, connections_found, recipient_name.
    """
    # ── Scrape ────────────────────────────────────────────────────────────────
    profile = _scrape_linkedin_profile(linkedin_url)

    if not profile:
        return {
            "message": None,
            "warning": "Could not fetch the LinkedIn profile. Make sure the URL is a valid public LinkedIn profile (e.g. linkedin.com/in/username).",
            "connections_found": [],
            "recipient_name": None,
        }

    # ── Company mismatch check ────────────────────────────────────────────────
    warning = None
    if _check_company_mismatch(profile, company):
        profile_name = profile.get("fullName") or profile.get("name") or "this person"
        warning = (
            f"Heads up — {profile_name}'s LinkedIn doesn't show them currently working at {company}. "
            f"You may have pasted the wrong profile."
        )

    # ── Find connections ──────────────────────────────────────────────────────
    connections = _find_connections(profile, gen_content)

    # ── Generate message via DeepSeek ─────────────────────────────────────────
    prompt = _build_referral_prompt(profile, gen_content, company, role, connections)

    agent = Agent(
        role="Referral Message Writer",
        goal="Write a highly personalised, human-sounding referral request message.",
        backstory="You write short, direct, personalised LinkedIn DMs that feel like they were typed by a real engineer — not generated by AI.",
        llm=deepseek_llm,
        verbose=False,
    )
    task = Task(
        description=prompt,
        expected_output="A 3-4 paragraph plain text referral request message.",
        agent=agent,
    )
    result = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False).kickoff()
    message = result.raw if hasattr(result, "raw") else str(result)

    recipient_name = profile.get("fullName") or profile.get("name")

    return {
        "message": message.strip(),
        "warning": warning,
        "connections_found": connections,
        "recipient_name": recipient_name,
    }
