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


def build_match_task(agent: Agent, gen_content: dict, ctc: dict, job: dict, preferences: dict | None = None, target_roles: list | None = None) -> Task:
    from jobs.scoring import extract_candidate_years, extract_required_years, calc_experience_score

    description = job.get("description") or ""

    # ── Pre-calculated deterministic scores ──────────────────────────────────
    candidate_years = extract_candidate_years(gen_content)
    min_req, max_req = extract_required_years(description)
    experience_score = calc_experience_score(candidate_years, min_req, max_req)

    # Build anchor block — only experience is deterministic; skills scored by LLM
    anchor_lines = []
    if experience_score is not None:
        req_str = f"{min_req}–{max_req}yr required" if max_req else f"{min_req}+yr required"
        anchor_lines.append(
            f"- experience: {experience_score} "
            f"(candidate has {candidate_years}yr, {req_str}) — USE THIS EXACT VALUE"
        )
    anchors_block = (
        "## Pre-calculated scores — copy these exact values into score_breakdown, do NOT change them\n"
        + "\n".join(anchor_lines)
        if anchor_lines
        else ""
    )

    # Dimensions DeepSeek must score itself
    llm_dimensions = ["role", "skills", "education", "company_type"]
    if experience_score is None:
        llm_dimensions.insert(1, "experience")

    # ── Compensation ──────────────────────────────────────────────────────────
    has_salary = bool(job.get("salary_range"))
    has_ctc = bool(ctc.get("current_base_in_lakhs") and ctc.get("expected_base_in_lakhs"))
    compensation_note = (
        f"Job salary range: {job['salary_range']}. "
        f"Candidate current: {ctc.get('current_base_in_lakhs')} LPA, "
        f"expected: {ctc.get('expected_base_in_lakhs')} LPA. "
        "Include compensation in score_breakdown."
        if has_salary and has_ctc
        else "No salary data available. Omit compensation from score_breakdown entirely."
    )

    # ── Preferences note ──────────────────────────────────────────────────────
    prefs = preferences or {}
    pref_lines = []
    if prefs.get("preferred_locations"):
        pref_lines.append(f"Preferred locations: {', '.join(prefs['preferred_locations'])}")
    if prefs.get("company_types"):
        pref_lines.append(f"Preferred company types: {', '.join(prefs['company_types'])} — weight company_type at 25% of final score")
    preferences_note = "\n".join(pref_lines) if pref_lines else "No specific preferences set."

    # Send skills + experience in full, truncate the rest
    skills_json = json.dumps(gen_content.get("skills", {}), indent=2)
    experience_json = json.dumps(gen_content.get("experience", []), indent=2)
    personal_json = json.dumps(gen_content.get("personal", {}), indent=2)
    education_json = json.dumps(gen_content.get("education", []), indent=2)

    target_roles_str = ", ".join(target_roles) if target_roles else "Not specified"

    return Task(
        description=f"""
Score how well this job matches the candidate's profile.

## Candidate Target Roles (what they are actively looking for)
{target_roles_str}

## Candidate Skills (complete — use this for skills scoring)
{skills_json}

## Candidate Experience
{experience_json[:2000]}

## Candidate Personal & Education
{personal_json}
{education_json}

## Job Details
Title: {job.get('title')}
Company: {job.get('company')}
Platform: {job.get('platform')}
Description: {description[:2500]}

## Compensation
{compensation_note}

## Candidate Preferences
{preferences_note}

{anchors_block}

## Your job — score ONLY these dimensions (0–10, one decimal):
{chr(10).join(f"- {d}" for d in llm_dimensions)}

Scoring guidance:
- role: how well the job title and responsibilities match the candidate's TARGET ROLES listed above and their past job titles. Score 9-10 if the job is exactly what they're targeting, 6-8 if closely related, below 5 if significantly different domain
- skills: look at the candidate's full skills list above vs the technologies/tools explicitly required in the JD. Score high (8-10) if the candidate has the core required stack, medium (5-7) if partial overlap, low (1-4) if major required skills are missing
- education: degree level and field alignment with job requirements
- company_type: does the candidate's background (startup/product/enterprise/service) match this company's type

## Final match_score
Weighted average of ALL dimensions (including pre-calculated ones).
Weights: role=30%, skills=25%, experience=25%, education=10%, company_type=10%.
If compensation is present, add it with 10% weight and reduce others proportionally.

Return ONLY a JSON object:
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


def _pick_top_projects(gen_content: dict, description: str, n: int = 3) -> list:
    """Score and return the top-n projects most relevant to the JD."""
    projects = gen_content.get("projects", []) or []
    if not projects:
        return []

    desc_lower = description.lower()
    scored = []
    for p in projects:
        stack = " ".join(p.get("techStack", []) or []).lower()
        name = (p.get("name") or "").lower()
        desc = (p.get("description") or "").lower()
        text = f"{name} {stack} {desc}"
        hits = sum(1 for word in text.split() if len(word) > 3 and word in desc_lower)
        scored.append((hits, p))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in scored[:n]]


def build_resume_task(agent: Agent, gen_content: dict, job: dict) -> Task:
    description = job.get("description") or ""
    top_projects = _pick_top_projects(gen_content, description, n=3)

    return Task(
        description=f"""
Generate a complete, tailored resume JSON for this specific job application.
Your goal: make this candidate look like the perfect hire for this exact role.
This resume must pass ATS keyword scanning AND impress a human reader.

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
Description: {description[:3000]}

## Projects to include (ONLY these {len(top_projects)} — pre-selected for relevance)
{json.dumps(top_projects, indent=2)}

## What you MUST do
1. Include EVERY experience entry from the source portfolio — do not drop any role.
2. Include ALL social links (linkedin, github, twitter, medium, website, etc.) from personal/social.
3. Read the job description carefully. Identify the 10-15 most important technical keywords and tools the JD requires. Every keyword from the candidate's existing skills that appears in the JD MUST appear naturally at least once in the resume (summary or bullets).
4. Rewrite basics.summary (3 sentences max, tight): sentence 1 — who the candidate is + years of experience + core domain; sentence 2 — the 2-3 most relevant technical strengths for THIS role using exact JD terminology; sentence 3 — one concrete impact statement (scale, business outcome, or metric).
5. Rewrite experience bullets to surface achievements most relevant to this JD. Use action verbs and exact terminology from the JD. Every bullet must feel written for this role.
6. Reorder skills categories — put what the JD cares about first. Include ALL skills from source.
7. Projects: use ONLY the pre-selected projects above. For each: description must be exactly 1 sentence (what it does + the scale or outcome). highlights must be 2-3 bullets — each with an action verb, a specific technical detail from the JD's required stack, and a measurable outcome or scope. No vague phrases like "built a system" or "worked on".
8. Use subjective framing freely: leadership, ownership, scale, cross-functional impact — if grounded in real experience.
9. Mirror the seniority tone of the job title (staff/senior/lead/principal — match their language).
10. Populate sortDate as YYYY-MM for all entries. Set endSortDate to "9999-12" for current roles.
11. Preserve the candidate's original experience role titles from the source portfolio. Do NOT rename titles into cleaner, broader, or more marketable variants.

## Hard rules — never break these
- NEVER add a technology, tool, or framework the candidate hasn't used.
- NEVER invent metrics, company names, or roles.
- NEVER rewrite experience job titles into nicer-sounding variants. Keep role naming consistent with the source portfolio.
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
8. ROLE TITLE CONSISTENCY — keep each experience role title aligned with the original source portfolio naming. Do not embellish or normalize titles unless the source itself differs.

Fix every issue you find. Return ONLY the corrected resume JSON. No explanation, no markdown.
""",
        expected_output="A complete, validated resume JSON with all issues fixed.",
        agent=agent,
    )


def build_general_resume_task(agent: Agent, gen_content: dict, target_roles: list[str]) -> Task:
    roles_str = ", ".join(target_roles) if target_roles else "software engineer"

    return Task(
        description=f"""
Generate a complete, all-purpose resume JSON for this candidate.
This is NOT for one company or one JD. It should work broadly across applications
for these target roles: {roles_str}

## Source Portfolio — use ALL of this, miss nothing
{json.dumps(gen_content, indent=2)[:6000]}

## Certifications (copy exactly into resume)
{json.dumps(gen_content.get('certifications', []))}

## Publications (copy exactly into resume)
{json.dumps(gen_content.get('publications', []))}

## Achievements (copy exactly into resume)
{json.dumps(gen_content.get('achievements', []))}

## What you MUST do
1. Include EVERY experience entry from the source portfolio — do not drop any role.
2. Include ALL social links (linkedin, github, twitter, medium, website, etc.) from personal/social.
3. Rewrite basics.summary as a strong all-purpose summary for the target roles above. It must be role-specific, keyword-rich, and reusable across many applications without naming any company.
4. Rewrite experience bullets to emphasise broad strengths: ownership, scale, systems design, execution, impact, and technologies repeatedly used in the source.
5. Reorder skills categories so the most marketable and role-relevant categories appear first. Include ALL skills from source.
6. Pick the 2-3 strongest projects for the target roles. Rewrite highlights to show relevance across those roles.
7. Keep the tone aligned with the candidate's actual seniority and most likely target roles.
8. Populate sortDate as YYYY-MM for all entries. Set endSortDate to "9999-12" for current roles.
9. Preserve the candidate's original experience role titles from the source portfolio. Do NOT rename titles into more generic or more polished variants.

## Hard rules — never break these
- NEVER add a technology, tool, or framework the candidate hasn't used.
- NEVER invent metrics, company names, or roles.
- NEVER rewrite experience job titles into nicer-sounding variants. Keep role naming consistent with the source portfolio.
- NEVER fabricate certifications or education.
- NEVER leave experience, skills, or education arrays empty.
- NEVER mention a specific employer or job description outside the candidate's real history.
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
        expected_output="A complete, valid JSON resume object for broad applications.",
        agent=agent,
    )


def build_general_resume_validation_task(
    agent: Agent,
    gen_content: dict,
    target_roles: list[str],
    resume_json: dict,
) -> Task:
    source_skills = []
    for group in gen_content.get("skills", []):
        source_skills.extend(group.get("items", []) if isinstance(group, dict) else [])
    source_companies = [e.get("company", "") for e in gen_content.get("experience", [])]
    source_projects = [p.get("name", "") for p in gen_content.get("projects", [])]
    roles_str = ", ".join(target_roles) if target_roles else "software engineer"

    return Task(
        description=f"""
Audit this generated all-purpose resume JSON and fix any issues. Return a corrected, complete resume JSON.

## Original Portfolio (source of truth)
Experience companies: {source_companies}
Projects: {source_projects}
All known skills/tools: {source_skills}
Social/personal: {json.dumps(gen_content.get('personal', {}), indent=2)}

## Target Roles
{roles_str}

## Generated Resume to Audit
{json.dumps(resume_json, indent=2)[:5000]}

## What to check and fix
1. COMPLETENESS — every experience from the source must appear. If any role is missing, add it back from the original portfolio.
2. NO INVENTED TECH — check every skill, tool, and technology in the resume against the known skills list. Remove any that don't appear in the source.
3. NO EMPTY ARRAYS — experience bullets, skills lists, and project highlights must not be empty. Populate from source if needed.
4. SOCIAL LINKS — all links (linkedin, github, twitter, medium, portfolio, website) from the original personal/social sections must be in basics.
5. SUMMARY — must be specific to the target roles above, not generic fluff and not tied to one company.
6. DATE FORMATS — all sortDate must be YYYY-MM. endSortDate must be "9999-12" for current roles.
7. SKILLS COMPLETENESS — all skill categories from the source must appear, reordered for the target roles.
8. ROLE TITLE CONSISTENCY — keep each experience role title aligned with the original source portfolio naming. Do not embellish or normalize titles unless the source itself differs.

Fix every issue you find. Return ONLY the corrected resume JSON. No explanation, no markdown.
""",
        expected_output="A complete, validated all-purpose resume JSON with all issues fixed.",
        agent=agent,
    )


def build_general_cover_letter_task(
    agent: Agent,
    gen_content: dict,
    target_roles: list[str],
) -> Task:
    personal = gen_content.get("personal", {})
    roles_str = ", ".join(target_roles) if target_roles else personal.get("title", "software engineer")

    return Task(
        description=f"""
Write a reusable, all-purpose cover letter for general job applications.
This is NOT for a specific company. It should be broadly reusable for these target roles:
{roles_str}

## Candidate
Name: {personal.get('name', '')}
Title: {personal.get('title', '')}
Bio: {personal.get('bio', '')}

## Source Portfolio
{json.dumps(gen_content, indent=2)[:4000]}

## Writing Rules
- Do NOT mention any company name, hiring manager, or specific job description
- Do NOT open with "I am writing to apply" or "I am excited to apply"
- 3-4 paragraphs: strong professional hook -> relevant background -> role fit/value -> direct CTA
- Make it specific to the target roles, domain strengths, and real experience
- Keep it natural and confident, not generic or AI-sounding
- Make it reusable as a strong base letter the user can lightly customize later

Output the cover letter as plain text only. No JSON. No headers.
""",
        expected_output=(
            "A 3-4 paragraph general-purpose cover letter in plain text with no formatting."
        ),
        agent=agent,
    )
