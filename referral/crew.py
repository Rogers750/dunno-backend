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
        backstory="You write short LinkedIn DMs that sound like a real person typed them quickly — warm, direct, human. You know how Indian engineers actually talk to each other.",
        llm=deepseek_llm,
        verbose=False,
    )

    task = Task(
        description=f"""
You have the raw copy-pasted text of a LinkedIn profile.
Parse it, find connections with the sender, then write a referral DM.

## Raw LinkedIn profile text
{profile_text[:4000]}

## Sender's background ({user_name})
Title: {user_title}
Bio: {user_bio}
Experience: {", ".join(user_exp)}
Education: {", ".join(user_edu)}

## Job they are applying for
Company: {company}
Role (short name only — do not use the full title in the message): {role}

---

## Step 1 — Parse the profile
Extract: recipient full name, current company, past companies, education institutions.

## Step 2 — Find shared connections
Compare with sender's background:
- Same college → "Same college: <name>"
- Same past company → "Both worked at: <name>"
Return empty list if none.

## Step 3 — Company mismatch check
If their current company clearly does NOT match "{company}", set warning:
"<name>'s profile doesn't seem to show them currently at {company}. You may have pasted the wrong profile."
Otherwise null.

## Step 4 — Estimate seniority
Estimate recipient's total years of experience from the profile text.
Sender ({user_name}) has ~{len(user_exp)} roles of experience.
Classify:
- "senior" → 5+ more years than sender, or Director/VP/Principal/Fellow title
- "peer" → within ~3 years of sender
- "junior" → less experience than sender

## Step 5 — Write the DM

This is a LinkedIn DM between two Indian engineers. It must feel like a real person typed it — not a template, not a cover letter excerpt. Before writing, ask: does this read as one connected thought, or 3 separate facts bolted together? If the latter, rewrite it.

### Seniority & language rules

**Junior (0-3 yrs, or clearly below sender's level)**
→ Use "tum/tumhara/tumko". Hinglish is natural, mix where it flows. Casual but not sloppy.

**Senior (4+ yrs, or clearly above sender's level)**
→ Use "aap/aapka/aapko" for any Hindi. Now flip a coin on language:
  - Sometimes write the whole message in clean professional English (no Hindi at all)
  - Sometimes write it as light Hinglish with aap
  Both are real. Alternating across users keeps it from looking templated. Pick one and commit.

**Same batch / similar experience**
→ Use "tum". Hinglish, feels like talking to a batchmate.

### How to build the message — 3 beats

**Beat 1 — The hook (1 sentence)**
Shared connection → open with it as a genuine observation. Feels like "oh I noticed this", not "I have identified we share X".
No shared connection → say something specific about their actual work that made you reach out to them in particular. Not flattery — observation.

**Beat 2 — The context (1 sentence)**
What you do + what you're going for. No tech stack. No full job title — use the short form ("data engineering role", "backend role"). Just enough for relevance.

**Beat 3 — The ask (1-2 sentences)**
Direct. Confident. Assume yes.
Good: "ek baar forward kar dena resume", "can you refer me or pass it along — sending resume now"
Offer to send resume immediately. No hedging.

### Banned phrases — regardless of seniority
- "I came across your profile"
- "hope this doesn't bother you"
- "I know you're busy"
- "it would mean a lot to me"
- "if possible", "no pressure", "no worries if not"
- any tech stack list
- years of experience as a number ("5 years", "3+ years")
- "resume attached" or any mention of attachment
- compliments directed at them ("your work is impressive", "I really admire")
- "I am reaching out", "I hope this finds you well", "passionate", "excited to", "leverage", "impactful", "synergy"

### Imperfection rule
Exactly one small natural error — a missing comma, a slightly run-on sentence, "toh" instead of "so", casual "kar" instead of "karna".
Never a spelling mistake on a name or company. Never broken grammar that makes meaning unclear.

### Hard rules
- First name only at the start. No "Hi", no "Dear".
- 80-100 words max.
- Plain text only. No formatting.

### Example (peer/junior, Hinglish)
BAD: "Rishabh, both of us at NIT Kurukshetra — dekha tumhara profile. tum JPMC mein ho, main apply kar raha hoon Software Engineer III - Data Engineering role. PySpark, AWS, Databricks ka hai."
GOOD: "Rishabh, randomly dekha tumhara profile — NIT Kurukshetra batch ho tum bhi. Im applying for a data engineering role at JPMC, exactly the kind of work you're doing there. Resume bhej raha hoon, ek baar team ko forward kar dena."

---

## Output — return ONLY this JSON, no markdown:
{{
  "recipient_name": "<string or null>",
  "connections_found": ["<string>", ...],
  "warning": "<string or null>",
  "seniority": "senior | peer | junior",
  "message": "<plain text DM>"
}}
""",
        expected_output="A JSON object with recipient_name, connections_found, warning, seniority, and message.",
        agent=agent,
    )

    result = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False).kickoff()
    raw = result.raw if hasattr(result, "raw") else str(result)

    raw = re.sub(r"^```(?:json)?\n?", "", raw.strip())
    raw = re.sub(r"\n?```$", "", raw.strip())

    try:
        return json.loads(raw)
    except Exception:
        logger.warning("[referral] DeepSeek returned non-JSON, wrapping as message")
        return {
            "recipient_name": None,
            "connections_found": [],
            "warning": None,
            "seniority": None,
            "message": raw.strip(),
        }
