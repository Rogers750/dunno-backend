import os
import json
import logging
from crewai import LLM, Crew, Agent, Task, Process

logger = logging.getLogger(__name__)

deepseek_llm = LLM(
    model="deepseek/deepseek-chat",
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)


def generate_referral_message(
    profile_text: str,
    company: str,
    role: str,
    gen_content: dict,
) -> dict:
    personal = gen_content.get("personal", {})
    user_name = personal.get("name", "")
    user_title = personal.get("title", "")
    user_bio = personal.get("bio", "")

    user_exp = []
    for exp in (gen_content.get("experience", []) or [])[:4]:
        user_exp.append(f"{exp.get('role')} at {exp.get('company')}")

    user_edu = []
    for edu in (gen_content.get("education", []) or []):
        user_edu.append(edu.get("institution") or edu.get("school") or "")

    agent = Agent(
        role="Referral Message Writer",
        goal="Parse a LinkedIn profile from raw pasted text, find shared connections with the sender, and write a personalised referral request DM.",
        backstory="You are an expert at reading messy copy-pasted LinkedIn text and writing short, human, direct messages that actually get replies.",
        llm=deepseek_llm,
        verbose=False,
    )

    task = Task(
        description=f"""
You have been given the raw text of a LinkedIn profile (copy-pasted by the user).
Your job is to:
1. Parse it to extract the person's name, current company, past companies, and education.
2. Find any shared connections with the sender's background.
3. Write a personalised referral request DM from the sender to this person.
4. Return a JSON object.

## Raw LinkedIn profile text (pasted by user)
{profile_text[:4000]}

## Sender's background ({user_name})
Title: {user_title}
Bio: {user_bio}
Experience: {", ".join(user_exp)}
Education: {", ".join(user_edu)}

## Job they are applying for
Company: {company}
Role: {role}

## Step 1 — Parse the profile
Extract from the raw text:
- recipient_name: the person's full name
- their current company
- their past companies (list)
- their education (list of institutions)

## Step 2 — Find shared connections
Compare extracted data against sender's background:
- Same college / university → "Same college: <name>"
- Same past company → "Both worked at: <name>"
List all matches. Empty list if none.

## Step 3 — Company mismatch check
If the person's current company clearly does NOT match "{company}", set warning to:
"<recipient_name>'s profile doesn't seem to show them currently working at {company}. You may have pasted the wrong profile."
Otherwise set warning to null.

## Step 4 — Write the referral DM
Rules:
- Address them by first name only
- If shared connections exist, lead with that — it's the strongest hook
- If no shared connections, open with something specific you noticed about their background
- Be direct: say you're applying for "{role}" at {company} and would appreciate a referral or internal intro
- Keep it short — 3-4 short paragraphs, this is a LinkedIn DM not an email
- Sound like a real person, not a template — no "I hope this message finds you well", no "I am reaching out to", no "I came across your profile"
- Slight informality is fine. Confident but not pushy
- End with a low-pressure ask: "happy to share my resume if helpful" or "no worries if it's not possible"
- No buzzwords, no "passionate about", no "excited to", no Steve Jobs language
- Plain text only — no subject line, no Dear/Hi header, just the message body

## Output — return ONLY this JSON, no markdown:
{{
  "recipient_name": "<string or null>",
  "connections_found": ["<string>", ...],
  "warning": "<string or null>",
  "message": "<plain text DM>"
}}
""",
        expected_output="A JSON object with recipient_name, connections_found, warning, and message.",
        agent=agent,
    )

    result = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False).kickoff()
    raw = result.raw if hasattr(result, "raw") else str(result)

    # Strip markdown fences if present
    import re
    raw = re.sub(r"^```(?:json)?\n?", "", raw.strip())
    raw = re.sub(r"\n?```$", "", raw.strip())

    try:
        return json.loads(raw)
    except Exception:
        # If JSON parse fails, return the raw text as message with empty metadata
        logger.warning("[referral] DeepSeek returned non-JSON, wrapping as message")
        return {
            "recipient_name": None,
            "connections_found": [],
            "warning": None,
            "message": raw.strip(),
        }
