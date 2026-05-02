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


def build_match_task(agent: Agent, gen_content: dict, ctc: dict, job: dict) -> Task:
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
Generate a tailored resume JSON for this specific job application.
Your goal is to make this candidate look like the ideal hire for this exact role.

## Source Portfolio (everything you have to work with)
{json.dumps(gen_content, indent=2)[:3000]}

## Target Job
Title: {job.get('title')}
Company: {job.get('company')}
Description: {(job.get('description') or '')[:2000]}

## What you MUST do
- Read the job description carefully. Extract the exact skills, keywords, and responsibilities they care about.
- Rewrite basics.summary to speak directly to this role — use the job's language, mirror their priorities, position the candidate as the answer to their problem.
- Rewrite experience bullets to surface achievements most relevant to this JD. Use action verbs and framing from the JD. Make every bullet feel like it was written for this role.
- Reorder skills to put the ones this job cares about first.
- Pick the 2-3 most relevant projects and rewrite their highlights to tie directly to what this job needs.
- Use subjective, role-appropriate framing freely: leadership, ownership, cross-functional collaboration, scale, impact — as long as it's grounded in the candidate's real experience.
- Mirror the seniority tone of the job (staff vs senior vs lead — match their language).

## Hard rules
- NEVER add a technical skill, tool, or technology the candidate has not worked with.
- NEVER invent metrics, companies, or roles that don't exist in the source portfolio.
- NEVER fabricate certifications or education.
- Everything subjective (framing, emphasis, tone) is fair game. Only facts are locked.

- Populate all sortDate fields as YYYY-MM
- Set endSortDate to "9999-12" for current/present positions
- Include optional sections (certifications, publications, achievements, languages)
  ONLY if they exist in the source portfolio

Return ONLY the resume JSON, no other text. Schema:
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
  "certifications": [],
  "publications": [],
  "achievements": [],
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


