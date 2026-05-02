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
Search all four job platforms (LinkedIn, Naukri, Wellfound, Instahyre) for live job
listings that match this candidate's profile.

## Candidate Profile
Target Roles: {roles_str}
Top Skills: {top_skills}
Experience: {years_hint}

## Instructions
1. For each platform, construct a focused search query combining the target role and
   top skills. Use all four tools — do not skip any platform.
2. Each tool handles deduplication and saves jobs to the database automatically.
3. Collect all job IDs returned by each tool.
4. Return a final summary: how many jobs were saved per platform, and the complete
   comma-separated list of all job IDs.

Return format:
LinkedIn: N jobs | Naukri: N jobs | Wellfound: N jobs | Instahyre: N jobs
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

## Source Portfolio
{json.dumps(gen_content, indent=2)[:3000]}

## Target Job
Title: {job.get('title')}
Company: {job.get('company')}
Description: {(job.get('description') or '')[:2000]}

## Instructions
- Reorder experience bullets to lead with the most relevant achievements for this role
- Reorder/filter skills to highlight what this job description emphasises
- Select 2-3 most relevant projects; rewrite highlights to tie to the job
- Rewrite basics.summary (3-4 sentences) specifically for this role and company
- Populate all sortDate fields as YYYY-MM
- Set endSortDate to "9999-12" for current/present positions
- Include optional sections (certifications, publications, achievements, languages)
  ONLY if they exist in the source portfolio
- Do NOT invent experience, metrics, or skills not present in the source portfolio

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


def build_pdf_render_task(agent: Agent, resume_json: dict) -> Task:
    return Task(
        description=f"""
Convert this resume JSON to ATS-friendly HTML suitable for PDF rendering.

## Resume Data
{json.dumps(resume_json, indent=2)[:4000]}

## HTML Requirements
- Single HTML file, self-contained (no external CSS/fonts/images)
- Black text on white background
- Standard system fonts only: Arial, Helvetica, Georgia
- Clean sections: Summary, Experience, Skills, Projects, Education
- No tables, no columns, no fancy layout — single column only
- Font size: name 18px bold, section headers 13px bold, body 11px
- All dates right-aligned on the same line as title/company
- Max width 800px, centered, padding 40px

Output ONLY the complete HTML document. Nothing else.
""",
        expected_output="A complete self-contained HTML document representing the resume.",
        agent=agent,
    )
