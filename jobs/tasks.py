import json
from crewai import Agent, Task

from jobs.schemas import MatchResult, CompanyInfo, ProjectSuggestions


def build_job_search_task(agent: Agent, target_roles: list, gen_content: dict) -> Task:
    skills_flat = []
    for group in gen_content.get("skills", []):
        skills_flat.extend(group.get("items", []))
    top_skills = ", ".join(skills_flat[:12])

    experience = gen_content.get("experience", [])
    years_hint = f"{len(experience)}+ roles" if experience else "unknown experience"

    roles_str = ", ".join(target_roles) if target_roles else "software engineer"

    return Task(
        description=f"""
Search two job platforms (LinkedIn and Google Jobs) for live job listings
that match this candidate's profile.

## Candidate Profile
Target Roles: {roles_str}
Top Skills: {top_skills}
Experience: {years_hint}

## Instructions
You have two tools available: LinkedIn Jobs Search, Google Jobs Search.
You MUST call both tools. Do not skip any.

1. Call "LinkedIn Jobs Search" with a query combining the target role and top skills.
2. Call "Google Jobs Search" with a query combining the target role and top skills.
3. Each tool saves jobs to the database and returns UUIDs. Collect all UUIDs.
4. Return the summary and all UUIDs.

Return format:
LinkedIn: N jobs | Google Jobs: N jobs
All job IDs: <uuid1>, <uuid2>, ...
""",
        expected_output=(
            "A summary line with counts per platform followed by a comma-separated "
            "list of all new job UUIDs saved to the database."
        ),
        agent=agent,
    )


def build_match_task(agent: Agent, gen_content: dict, ctc: dict, job: dict, preferences: dict | None = None) -> Task:
    has_salary = bool(job.get("salary_range"))
    has_ctc = bool(ctc.get("current_base_in_lakhs") and ctc.get("expected_base_in_lakhs"))
    compensation_note = (
        f"Job salary range: {job['salary_range']}. "
        f"Candidate current: {ctc.get('current_base_in_lakhs')} LPA, "
        f"expected: {ctc.get('expected_base_in_lakhs')} LPA. "
        "Include compensation in score_breakdown."
        if has_salary and has_ctc
        else "No salary data available for one or both parties. Omit compensation from score_breakdown entirely."
    )

    prefs = preferences or {}
    pref_lines = []
    if prefs.get("preferred_locations"):
        pref_lines.append(f"Preferred locations: {', '.join(prefs['preferred_locations'])}")
    if prefs.get("company_types"):
        pref_lines.append(f"Preferred company types: {', '.join(prefs['company_types'])} — weight company_type dimension at 25% of final score")
    if prefs.get("min_experience") is not None or prefs.get("max_experience") is not None:
        pref_lines.append(f"Experience range: {prefs.get('min_experience', 0)}–{prefs.get('max_experience', '∞')} years")
    preferences_note = "\n".join(pref_lines) if pref_lines else "No specific preferences set."

    return Task(
        description=f"""
Score how well this job matches the candidate's profile.

## Candidate Portfolio
{json.dumps(gen_content, indent=2)[:3000]}

## Job Details
Title: {job.get('title')}
Company: {job.get('company')}
Platform: {job.get('platform')}
Description: {(job.get('description') or '')[:2000]}

## Compensation
{compensation_note}

## Candidate Preferences (factor these into scoring weights)
{preferences_note}

## Scoring Instructions
Score each dimension 0–10 (float, one decimal):
- role: how well the job title/responsibilities match the candidate's target roles and experience
- skills: overlap between job requirements and candidate's proven skills
- experience: years of experience required vs candidate's actual years
- education: degree/field alignment
- company_type: startup/enterprise/product/service fit based on candidate's background
- compensation: only include if salary data is available for both parties

Final match_score = weighted average (you decide weights based on what matters most).

Return ONLY a JSON object matching this schema:
{{
  "match_score": <float>,
  "score_breakdown": {{
    "role": <float>,
    "skills": <float>,
    "experience": <float>,
    "education": <float>,
    "company_type": <float>,
    "compensation": <float or null>
  }}
}}
""",
        expected_output="A JSON object with match_score and score_breakdown.",
        agent=agent,
        output_pydantic=MatchResult,
    )


def build_company_research_task(agent: Agent, company_name: str) -> Task:
    return Task(
        description=f"""
Look up "{company_name}" on Glassdoor using the Glassdoor Company Lookup tool.

Extract:
- glassdoor_rating (float, e.g. 4.2) — null if not found
- description (string, 1-2 sentences) — null if not found
- culture_notes (string, key culture highlights) — null if not found
- size (string, e.g. "1001-5000 employees") — null if not found
- founded (string, e.g. "2015") — null if not found

If the company is not on Glassdoor, return all fields as null.
Never fabricate any data.

Return ONLY a JSON object matching this schema:
{{
  "glassdoor_rating": <float or null>,
  "description": <string or null>,
  "culture_notes": <string or null>,
  "size": <string or null>,
  "founded": <string or null>
}}
""",
        expected_output="A JSON object with Glassdoor company data, all fields nullable.",
        agent=agent,
        output_pydantic=CompanyInfo,
    )


def build_resume_task(agent: Agent, gen_content: dict, job: dict) -> Task:
    return Task(
        description=f"""
Generate a complete, tailored resume JSON for this specific job application.
Your goal: make this candidate look like the perfect hire for this exact role.

## Source Portfolio — use ALL of this, miss nothing
{json.dumps(gen_content, indent=2)[:6000]}

## Certifications (copy exactly into resume)
{json.dumps(gen_content.get('certifications', []))}

## Publications (copy exactly into resume)
{json.dumps(gen_content.get('publications', []))}

## Achievements (copy exactly into resume)
{json.dumps(gen_content.get('achievements', []))}

## Target Job
Title: {job.get('title')}
Company: {job.get('company')}
Description: {(job.get('description') or '')[:3000]}

## What you MUST do
1. Include EVERY experience entry from the source portfolio — do not drop any role.
2. Include ALL social links (linkedin, github, twitter, medium, website, etc.) from personal/social.
3. Rewrite basics.summary (4-5 sentences) to speak directly to this role — use the job's exact language, mirror their priorities, position the candidate as the answer to their specific problem.
4. Rewrite experience bullets to surface achievements most relevant to this JD. Use action verbs and framing from the JD. Every bullet must feel written for this role.
5. Reorder skills categories — put what the JD cares about first. Include ALL skills from source.
6. Pick 2-3 most relevant projects. Rewrite highlights to tie directly to the job needs.
7. Use subjective framing freely: leadership, ownership, scale, cross-functional impact — if grounded in real experience.
8. Mirror the seniority tone of the job title (staff/senior/lead/principal — match their language).
9. Populate sortDate as YYYY-MM for all entries. Set endSortDate to "9999-12" for current roles.

## Hard rules — never break these
- NEVER add a technology, tool, or framework the candidate hasn't used.
- NEVER invent metrics, company names, or roles.
- NEVER fabricate certifications or education.
- NEVER leave experience, skills, or education arrays empty.
- certifications, publications, achievements: copy exactly from source portfolio if present. If source has none, return empty array []. ALWAYS include these keys.

Return ONLY the resume JSON. No markdown, no explanation. Schema:
{{
  "basics": {{
    "name": "", "title": "", "email": "", "phone": "", "location": "",
    "summary": "", "linkedin": "", "github": "", "portfolio": ""
  }},
  "experience": [{{
    "company": "", "role": "", "location": "", "employmentType": "",
    "isRemote": false, "startDate": "", "endDate": "",
    "sortDate": "YYYY-MM", "endSortDate": "YYYY-MM or 9999-12",
    "bullets": []
  }}],
  "education": [{{
    "institution": "", "degree": "", "startDate": "", "endDate": "",
    "sortDate": "YYYY-MM", "endSortDate": "YYYY-MM", "gpa": "", "honors": "", "activities": ""
  }}],
  "skills": {{
    "languages": [], "frameworks": [], "tools": [], "concepts": []
  }},
  "projects": [{{
    "name": "", "description": "", "techStack": [], "link": "",
    "startDate": "", "endDate": "", "sortDate": "YYYY-MM", "endSortDate": "YYYY-MM",
    "highlights": []
  }}],
  "certifications": [{{ "name": "", "issuer": "", "year": "" }}],
  "publications": [{{ "title": "", "url": "", "year": "" }}],
  "achievements": ["string"],
  "languages": []
}}
""",
        expected_output="A complete, valid JSON resume object tailored to the specified job.",
        agent=agent,
    )


def build_cover_letter_task(
    agent: Agent,
    gen_content: dict,
    job: dict,
    company_info: dict,
) -> Task:
    personal = gen_content.get("personal", {})
    return Task(
        description=f"""
Write a cover letter for this job application.

## Candidate
Name: {personal.get('name', '')}
Title: {personal.get('title', '')}
Bio: {personal.get('bio', '')}

## Target Job
Title: {job.get('title')}
Company: {job.get('company')}
Description: {(job.get('description') or '')[:1500]}

## Company Intelligence (from Glassdoor)
Rating: {company_info.get('glassdoor_rating', 'N/A')}
About: {company_info.get('description', 'N/A')}
Culture: {company_info.get('culture_notes', 'N/A')}

## Writing Rules
- Do NOT open with "I am writing to apply" or "I am excited to apply"
- Open with a specific hook — reference something concrete about the company or role
- 3-4 paragraphs: hook → relevant background → why this company specifically → CTA
- Use first person, confident tone, natural language
- Reference culture_notes or company description to show genuine interest
- End with a clear, direct call to action
- Must not read as AI-generated — avoid buzzwords, passive voice, hollow phrases

Output the cover letter as plain text only. No JSON. No headers.
""",
        expected_output=(
            "A 3-4 paragraph cover letter in plain text. No formatting, no JSON, "
            "no 'Dear Hiring Manager' header — just the letter body."
        ),
        agent=agent,
    )


def build_project_advisor_task(agent: Agent, gen_content: dict, job: dict) -> Task:
    existing = [p.get("name", "") for p in gen_content.get("projects", [])]
    existing_str = ", ".join(existing) if existing else "none"

    return Task(
        description=f"""
Suggest exactly 3 projects the candidate should build to strengthen their application.

## Target Job
Title: {job.get('title')}
Company: {job.get('company')}
Description: {(job.get('description') or '')[:1500]}

## Candidate's Existing Projects (do NOT suggest these)
{existing_str}

## Instructions
- Suggest exactly 3 projects not already in the candidate's portfolio
- Each project must be directly relevant to this specific job description
- Estimate realistic build time assuming active AI assistance (Cursor, Claude, etc.)
- difficulty must be one of: easy | medium | hard

Return ONLY a JSON object:
{{
  "suggestions": [
    {{
      "name": "",
      "description": "",
      "difficulty": "easy|medium|hard",
      "ai_build_time": "e.g. 2-3 days",
      "why_relevant": ""
    }}
  ]
}}
""",
        expected_output="A JSON object with exactly 3 project suggestions.",
        agent=agent,
        output_pydantic=ProjectSuggestions,
    )


def build_resume_validation_task(agent: Agent, gen_content: dict, job: dict, resume_json: dict) -> Task:
    source_skills = []
    for group in gen_content.get("skills", []):
        source_skills.extend(group.get("items", []) if isinstance(group, dict) else [])
    source_companies = [e.get("company", "") for e in gen_content.get("experience", [])]
    source_projects = [p.get("name", "") for p in gen_content.get("projects", [])]

    return Task(
        description=f"""
Audit this generated resume JSON and fix any issues. Return a corrected, complete resume JSON.

## Original Portfolio (source of truth)
Experience companies: {source_companies}
Projects: {source_projects}
All known skills/tools: {source_skills}
Social/personal: {json.dumps(gen_content.get('personal', {}), indent=2)}

## Target Job
Title: {job.get('title')}
Company: {job.get('company')}

## Generated Resume to Audit
{json.dumps(resume_json, indent=2)[:5000]}

## What to check and fix
1. COMPLETENESS — every experience from the source must appear. If any role is missing, add it back from the original portfolio.
2. NO INVENTED TECH — check every skill, tool, and technology in the resume against the known skills list. Remove any that don't appear in the source.
3. NO EMPTY ARRAYS — experience bullets, skills lists, and project highlights must not be empty. Populate from source if needed.
4. SOCIAL LINKS — all links (linkedin, github, twitter, medium, portfolio, website) from the original personal section must be in basics.
5. SUMMARY — must be specific to the target job, not generic. If it's generic, rewrite it.
6. DATE FORMATS — all sortDate must be YYYY-MM. endSortDate must be "9999-12" for current roles.
7. SKILLS COMPLETENESS — all skill categories from the source must appear, reordered by JD relevance.

Fix every issue you find. Return ONLY the corrected resume JSON. No explanation, no markdown.
""",
        expected_output="A complete, validated resume JSON with all issues fixed.",
        agent=agent,
    )


