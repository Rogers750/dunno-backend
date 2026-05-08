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

This is a LinkedIn DM between two Indian engineers. It should feel like a real person typed it — not a template, not a cover letter excerpt.

**Before writing, ask yourself: does this message flow as one connected thought, or does it feel like 3 separate facts bolted together?** If the latter, rewrite it.

### Tone by seniority

**senior** → English only. Composed, warm, direct. If any Hindi word slips in naturally, use aap/aapka/aapko — never tum. Don't force Hindi.

**peer / junior** → Hinglish. Mix naturally — not every sentence needs Hindi, just where it flows. Use tum/tumhara/tumko for Hindi pronouns, never aap. No slang ("yaar", "bhai") — keep it professional even in Hinglish.

### How to build the message — 3 beats

**Beat 1 — The hook**
If shared connection exists: open with it as a genuine observation, not a statement of fact. It should feel like "oh I noticed this" not "I have identified that we share X". One sentence.
If no shared connection: say something specific about what they actually work on that made you reach out to them specifically — not generic flattery.

**Beat 2 — The context**
What you do + what you're going for. One sentence. Do NOT list technologies. Do NOT use the full job title. Describe the work: "data engineering role", "backend role", "analytics role". Just enough for them to know why it's relevant.

**Beat 3 — The ask**
Direct. Confident. Assume they'll say yes.
Good: "ek baar resume forward kar dena", "can you refer me or pass it to the team — sending resume right now"
Bad: "if possible", "no pressure", "no worries if not", "would it be okay if" — these all go in the bin.
End by offering to send the resume immediately.

### Hard rules — no exceptions
- First name only at the start. No "Hi", no "Dear", no greeting word.
- NEVER list the tech stack in the message
- NEVER use the full job title — shorten it
- The message must read as one connected thought, not disconnected bullet sentences
- 1 deliberate small imperfection — a missing apostrophe (dont, Im, its) or a very slight run-on. Just one.
- 80-100 words. Tight.
- NEVER use: "I am reaching out", "I came across your profile", "I hope this finds you well", "passionate", "excited to", "leverage", "impactful", "transformative", "synergy", "as per", "please revert"
- Plain text only. No formatting.

### Examples of tone (peer/junior, Hinglish)
BAD: "Rishabh, both of us at NIT Kurukshetra — dekha tumhara profile. tum JPMC mein ho, main apply kar raha hoon Software Engineer III - Data Engineering role. PySpark, AWS, Databricks ka hai."
GOOD: "Rishabh, randomly dekha tumhara profile — NIT Kurukshetra batch ho tum bhi. Im applying for a data engineering role at JPMC, exactly the kind of work you're doing there. Resume bhej raha hoon, ek baar team ko forward kar dena."

Notice what changed: the good version flows as one thought, doesnt list tech, shortens the title, and the ask comes naturally at the end.

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
