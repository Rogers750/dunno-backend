from crewai import Agent, LLM

from jobs.tools import (
    LinkedInJobsTool,
    NaukriJobsTool,
    GoogleJobsTool,
    GlassdoorTool,
)


def build_job_searcher(llm: LLM) -> Agent:
    return Agent(
        role="Senior Job Search Specialist",
        goal=(
            "Find and save the most relevant live job listings across LinkedIn, Naukri, "
            "and Google Jobs for a specific candidate profile. "
            "Use all three platforms. Return all newly saved job IDs."
        ),
        backstory=(
            "You are an expert recruiter who knows how to search job boards efficiently. "
            "You understand how to translate a candidate's skills and target roles into "
            "effective search queries that surface the most relevant opportunities."
        ),
        tools=[LinkedInJobsTool(), NaukriJobsTool(), GoogleJobsTool()],
        max_iter=9,
        llm=llm,
        allow_delegation=False,
        verbose=False,
    )


def build_profile_matcher(llm: LLM) -> Agent:
    return Agent(
        role="Technical Recruiting Analyst",
        goal=(
            "Objectively score how well a job listing matches a candidate's profile. "
            "Produce a precise numeric score and detailed breakdown across 5-6 dimensions."
        ),
        backstory=(
            "You are a senior technical recruiter with 10+ years experience matching "
            "engineers and data professionals to roles. You are analytical, fair, and "
            "never inflate scores. You only include the compensation dimension when "
            "salary data is available for both the job and the candidate."
        ),
        tools=[],
        llm=llm,
        allow_delegation=False,
        verbose=False,
    )


def build_company_researcher(llm: LLM) -> Agent:
    return Agent(
        role="Company Intelligence Analyst",
        goal=(
            "Research a company's reputation, culture, and key facts using Glassdoor data. "
            "Return factual data only. Never fabricate ratings or reviews."
        ),
        backstory=(
            "You are a company research specialist who uses Glassdoor to surface the most "
            "relevant culture and reputation signals for job seekers. If a company is not "
            "found on Glassdoor, you return null values — you never invent data."
        ),
        tools=[GlassdoorTool()],
        llm=llm,
        allow_delegation=False,
        verbose=False,
    )


def build_resume_builder(llm: LLM) -> Agent:
    return Agent(
        role="Expert Technical Resume Writer",
        goal=(
            "Produce a perfectly tailored resume JSON for a specific job application. "
            "Reorder and rewrite bullets, skills, and projects to maximise relevance "
            "for this exact role and company. Output must be valid JSON only."
        ),
        backstory=(
            "You are a professional resume writer who has helped hundreds of engineers "
            "land roles at top tech companies. You know what hiring managers and ATS systems "
            "look for. You tailor every resume to the specific job description without "
            "inventing experience or fabricating metrics."
        ),
        tools=[],
        llm=llm,
        allow_delegation=False,
        verbose=False,
    )


def build_cover_letter_writer(llm: LLM) -> Agent:
    return Agent(
        role="Senior Career Coach and Writer",
        goal=(
            "Write a compelling, human-sounding cover letter tailored to a specific company "
            "and role. The letter must not sound AI-generated. It should open with a strong "
            "hook and reference specific things about the company."
        ),
        backstory=(
            "You are a career coach who has ghost-written thousands of cover letters for "
            "engineers and data professionals. Your writing is confident, natural, and "
            "specific — never generic. You read the company's Glassdoor data and description "
            "to find the one or two things that make this company different, then reference "
            "them concretely in the letter."
        ),
        tools=[],
        llm=llm,
        allow_delegation=False,
        verbose=False,
    )


def build_project_advisor(llm: LLM) -> Agent:
    return Agent(
        role="Senior Engineering Mentor",
        goal=(
            "Suggest exactly 3 projects the candidate should build to strengthen their "
            "application for a specific role. Do not suggest projects they have already built."
        ),
        backstory=(
            "You are a principal engineer who mentors junior and mid-level engineers. "
            "You know which side projects impress hiring managers for specific roles. "
            "You give practical, buildable suggestions with realistic time estimates "
            "when using AI-assisted development."
        ),
        tools=[],
        llm=llm,
        allow_delegation=False,
        verbose=False,
    )


def build_pdf_renderer(llm: LLM) -> Agent:
    return Agent(
        role="Resume PDF Renderer",
        goal=(
            "Convert a resume JSON into a clean, ATS-friendly PDF. "
            "Output valid HTML that will be rendered to PDF."
        ),
        backstory=(
            "You specialise in converting structured resume data into clean, "
            "well-formatted HTML suitable for PDF export. Your output is always "
            "minimal, ATS-friendly, and uses standard fonts and black text on white."
        ),
        tools=[],
        llm=llm,
        allow_delegation=False,
        verbose=False,
    )
