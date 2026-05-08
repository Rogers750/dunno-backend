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

## Step 4 — Estimate seniority gap
From the raw profile text, estimate the recipient's total years of professional experience.
The sender ({user_name}) has approximately {len(user_exp)} roles worth of experience.

Classify the seniority gap:
- "senior" → recipient has 5+ more years of experience than the sender, OR holds a Director/VP/Principal/Fellow title
- "peer" → within ~3 years of the sender's experience, or similar level
- "junior" → recipient has less experience than the sender

## Step 5 — Write the referral DM
You are writing this as {user_name}, a real Indian engineer messaging another Indian engineer on LinkedIn.

**Tone based on seniority gap:**

If "senior" — English only. Respectful but direct. No slang. Still human and warm, not robotic. Exception: if you do use any Hindi words for a senior, ALWAYS use "aap/aapka/aapko" — never "tum/tumhara". Example: "aapka profile dekha", "ek baar aap forward kar dein".
If "peer" — Mix English and Hindi casually (Hinglish). Use "tum/tumhara/tumko". No slang like "yaar" or "bhai". Good examples: "dekha tumhara profile", "tumse connect karna tha", "ek baar forward kar dena", "resume bhej sakta hoon".
If "junior" — Same Hinglish style as peer. Use "tum/tumhara/tumko". Can be slightly more casual in tone.

**The ask — always direct, never weak:**
- Do NOT say "if possible", "no pressure", "no worries if not", "totally understand if you can't" — these kill momentum
- The ask should assume they will help, not ask permission: "ek baar forward kar dena", "can you refer me or pass this along", "would really help if you could put in a word"
- Make it easy for them to say yes — offer to send resume immediately

**All tones — hard rules:**
- Address by first name only, no "Hi" or "Dear" opener
- Start with the shared connection if one exists — jump straight into it, no warm-up
- If no shared connection, open with something specific and genuine about their work
- Mention the job by short name only — never paste the full job title
- Make 1 small natural typo — a missing apostrophe ("dont", "Im", "its"), or a lowercase start — one is enough
- Vary sentence length. Short punchy ones mixed with longer ones. Not uniform rhythm.
- Flow like thoughts, not paragraphs
- Under 100 words total
- NEVER use: "I am reaching out", "I came across your profile", "I hope this finds you well", "passionate", "excited to", "leverage", "impactful", "transformative", "synergy"
- Plain text only — no subject line, no greeting header, just the message body

## Output — return ONLY this JSON, no markdown:
{{
  "recipient_name": "<string or null>",
  "connections_found": ["<string>", ...],
  "warning": "<string or null>",
  "seniority": "senior | peer | junior",
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
