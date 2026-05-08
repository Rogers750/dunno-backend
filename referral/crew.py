import os
import re
import json
import logging
from crewai import LLM, Crew, Agent, Task, Process

logger = logging.getLogger(__name__)

deepseek_llm = LLM(
    model="deepseek/deepseek-chat",
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)

deepseek_reasoner_llm = LLM(
    model="deepseek/deepseek-reasoner",
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)


def _truncate_profile(text: str, max_chars: int = 4000) -> str:
    """Truncate at last newline before max_chars to avoid mid-sentence cuts."""
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars]
    last_newline = truncated.rfind("\n")
    return truncated[:last_newline] if last_newline != -1 else truncated


def _parse_json_result(raw_result) -> dict:
    """Safely extract and parse JSON from a CrewAI result."""
    raw = raw_result.raw if hasattr(raw_result, "raw") else str(raw_result)
    raw = re.sub(r"^```(?:json)?\n?", "", raw.strip())
    raw = re.sub(r"\n?```$", "", raw.strip())
    return json.loads(raw)


def _determine_seniority(
    parsed: dict,
    user_total_exp: float,
) -> str:
    """
    Determine seniority in Python — not the LLM's job.
    Uses actual years of experience and title signals.
    """
    recipient_years = parsed.get("recipient_years_experience") or 0
    seniority_title = (parsed.get("recipient_seniority_title") or "").lower()

    senior_title_keywords = [
        "director", "vp", "vice president", "principal",
        "fellow", "head of", "staff engineer", "distinguished",
    ]
    is_senior_title = any(t in seniority_title for t in senior_title_keywords)

    if is_senior_title or recipient_years >= (user_total_exp + 4):
        return "senior"
    elif recipient_years < max(user_total_exp - 2, 1):
        return "junior"
    else:
        return "peer"


def _build_lang_instruction(seniority: str) -> str:
    """Always English — clean, direct, human. No Hindi, no Hinglish."""
    return "Write in English only. No Hindi words, no Hinglish. Keep it natural and human, not corporate."


def generate_referral_message(
    profile_text: str,
    company: str,
    role: str,
    gen_content: dict,
) -> dict:
    # ── Extract sender context ──────────────────────────────────────────────
    personal = gen_content.get("personal", {})
    user_name = personal.get("name", "")
    user_title = personal.get("title", "")

    # Use actual total_years_experience if available — don't proxy from role count
    user_total_exp = float(gen_content.get("total_years_experience") or 0)
    if user_total_exp == 0:
        # fallback: rough estimate from number of experience entries
        user_total_exp = len(gen_content.get("experience", []) or []) * 1.5

    user_exp = []
    for exp in (gen_content.get("experience", []) or [])[:4]:
        user_exp.append(f"{exp.get('role')} at {exp.get('company')}")

    user_edu = []
    for edu in (gen_content.get("education", []) or []):
        user_edu.append(edu.get("institution") or edu.get("school") or "")

    profile_snippet = _truncate_profile(profile_text, max_chars=4000)

    # ── Agent 1: Parser (reasoner — needs to infer structure from messy text) ──
    parse_agent = Agent(
        role="Profile Parser",
        goal="Extract clean structured data from raw LinkedIn profile text.",
        backstory="You extract structured data accurately from messy copy-pasted text. You are precise and never hallucinate missing fields.",
        llm=deepseek_reasoner_llm,
        verbose=False,
    )

    parse_task = Task(
        description=(
            "Extract structured data from this raw copy-pasted LinkedIn profile text.\n\n"
            f"## Raw LinkedIn profile text\n{profile_snippet}\n\n"
            f"## Sender background\n"
            f"Name: {user_name}\n"
            f"Experience: {', '.join(user_exp)}\n"
            f"Education: {', '.join(user_edu)}\n\n"
            f"## Target company: {company}\n\n"
            "Instructions:\n"
            "- connections_found: compare recipient's companies + education against sender's. "
            "Only include if genuinely shared. Format: 'Same college: X' or 'Both worked at: X'.\n"
            f"- company_mismatch: true if recipient's CURRENT company does NOT match '{company}'.\n"
            "- recipient_years_experience: estimate total years from career history dates. Integer.\n"
            "- recipient_seniority_title: their most senior title (Director, VP, Staff Engineer, etc.) or null.\n\n"
            "Return ONLY valid JSON, no markdown fences, no explanation:\n"
            '{\n'
            '  "recipient_name": "<full name or null>",\n'
            '  "recipient_first_name": "<first name only or null>",\n'
            '  "current_company": "<current company or null>",\n'
            '  "past_companies": ["..."],\n'
            '  "education": ["..."],\n'
            '  "recipient_years_experience": <int>,\n'
            '  "recipient_seniority_title": "<title or null>",\n'
            '  "connections_found": ["..."],\n'
            '  "company_mismatch": true_or_false\n'
            '}'
        ),
        expected_output=(
            "Valid JSON object with all fields. "
            "No markdown, no explanation, no extra text before or after the JSON."
        ),
        agent=parse_agent,
    )

    parse_result = Crew(
        agents=[parse_agent],
        tasks=[parse_task],
        process=Process.sequential,
        verbose=False,
    ).kickoff()

    try:
        parsed = _parse_json_result(parse_result)
    except Exception:
        logger.warning("[referral] parse agent returned non-JSON — aborting")
        return {
            "recipient_name": None,
            "connections_found": [],
            "warning": "Could not parse the LinkedIn profile. Please check the pasted text.",
            "seniority": None,
            "message": None,
        }

    # ── Extract parsed fields ───────────────────────────────────────────────
    recipient_name = parsed.get("recipient_name")
    recipient_first_name = (
        parsed.get("recipient_first_name")
        or (recipient_name.split()[0] if recipient_name else None)
    )

    if not recipient_first_name:
        logger.warning("[referral] could not determine recipient first name")
        return {
            "recipient_name": None,
            "connections_found": [],
            "warning": "Could not identify the recipient's name from the profile. Please check the pasted text.",
            "seniority": None,
            "message": None,
        }

    connections_found = parsed.get("connections_found") or []
    company_mismatch = parsed.get("company_mismatch", False)

    # ── Seniority + language — resolved in Python ───────────────────────────
    seniority = _determine_seniority(parsed, user_total_exp)
    lang_instruction = _build_lang_instruction(seniority)

    # ── Warning ─────────────────────────────────────────────────────────────
    warning = None
    if company_mismatch:
        warning = (
            f"{recipient_name or 'This person'}'s profile doesn't seem to show them "
            f"currently at {company}. You may have pasted the wrong profile."
        )

    connections_str = (
        "\n".join(f"- {c}" for c in connections_found)
        if connections_found
        else "None found"
    )

    hook_instruction = (
        "Open with the shared connection as a genuine moment of recognition — "
        "feels like 'oh I noticed this', not a formal statement of fact."
        if connections_found
        else (
            "No shared connection exists. Open with something specific about their "
            "actual work or role that made you reach out to them in particular. "
            "Observation, not flattery."
        )
    )

    # ── Agent 2: Writer (chat — needs to follow creative instructions, not reason) ──
    write_agent = Agent(
        role="Referral Message Writer",
        goal="Write a short, human, personalised LinkedIn referral DM.",
        backstory=(
            "You write LinkedIn DMs that sound exactly like a real Indian engineer "
            "typed them — warm, direct, flows as one connected thought. "
            "Never sounds like a template or a cover letter."
        ),
        llm=deepseek_llm,  # chat model — better at following stylistic instructions
        verbose=False,
    )

    banned_phrases = (
        "NEVER USE any of these: "
        "'I came across your profile', 'hope this doesnt bother you', "
        "'I know youre busy', 'it would mean a lot', 'if possible', "
        "'no pressure', 'no worries if not', 'I am reaching out', "
        "'passionate', 'excited to', 'impactful', 'synergy', "
        "'resume attached', any tech stack list, years of experience as a number, "
        "compliments directed at the recipient."
    )

    write_task = Task(
        description=(
            f"Write a LinkedIn referral DM from {user_name} to {recipient_first_name}.\n\n"
            f"SENDER: {user_name} ({user_title})\n"
            f"RECIPIENT: {recipient_name}, seniority level: {seniority}\n"
            f"SHARED CONNECTIONS:\n{connections_str}\n"
            f"JOB: a {role.split()[0].lower()} role at {company} "
            f"— use a short natural form like 'data engineering role' or 'backend role', "
            f"never the full job title\n\n"
            f"LANGUAGE RULE (follow exactly): {lang_instruction}\n\n"
            f"HOOK RULE: {hook_instruction}\n\n"
            "MESSAGE STRUCTURE — must flow as ONE connected thought, not 3 separate facts:\n"
            "  Beat 1 (1 sentence): Hook — shared connection or specific observation\n"
            f"  Beat 2 (1 sentence): What {user_name} does + the role they're applying for. No tech stack.\n"
            "  Beat 3 (1-2 sentences): The ask — direct, confident, assume yes. "
            "Offer resume immediately. Two options in ask: refer me, or pass to right person.\n"
            "  Good ask examples: 'resume bhej raha hoon, ek baar forward kar dena' / "
            "'can you refer me or pass it to someone who can — sending resume now'\n\n"
            f"FORMAT RULES:\n"
            f"  - Start with exactly: '{recipient_first_name},' — no Hi, no Dear, no Hey\n"
            "  - 80-100 words max. Count before returning.\n"
            "  - Plain text only. No bullet points, no bold, no formatting.\n"
            "  - Exactly ONE natural imperfection: missing apostrophe (dont/Im/its) "
            "OR 'toh' instead of 'so' OR a slight run-on. One only, never on a name.\n\n"
            f"{banned_phrases}\n\n"
            "GOOD EXAMPLE:\n"
            "'Rishabh, randomly saw your profile — didnt realise you went to NIT Kurukshetra too. "
            "Im applying for a data engineering role at JPMC, exactly the kind of work "
            "you're doing there. Sending my resume now, can you pass it along or refer me?'\n\n"
            "Output the message ONLY. "
            "No intro sentence, no explanation, no quotes around it. "
            f"First word must be '{recipient_first_name},'."
        ),
        expected_output=(
            f"Only the DM as plain text, 80-100 words. "
            f"Starts with '{recipient_first_name},' and nothing else before it. "
            "No explanation, no wrapper text, no quotes around the message."
        ),
        agent=write_agent,
    )

    write_result = Crew(
        agents=[write_agent],
        tasks=[write_task],
        process=Process.sequential,
        verbose=False,
    ).kickoff()

    message = write_result.raw if hasattr(write_result, "raw") else str(write_result)

    return {
        "recipient_name": recipient_name,
        "connections_found": connections_found,
        "warning": warning,
        "seniority": seniority,
        "message": message.strip(),
    }