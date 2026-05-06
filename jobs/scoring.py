import re
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


# ── Date parsing ──────────────────────────────────────────────────────────────

def _parse_date(s: str) -> datetime | None:
    if not s:
        return None
    s = s.strip()
    for fmt in ("%Y-%m", "%b %Y", "%B %Y", "%Y"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


# ── Candidate experience ──────────────────────────────────────────────────────

def extract_candidate_years(gen_content: dict) -> float:
    """Sum experience durations from gen_content dates. Returns total years as float."""
    experience = gen_content.get("experience", [])
    if not experience:
        return 0.0

    now = datetime.now()
    total_months = 0

    for role in experience:
        start_str = role.get("startDate") or role.get("sortDate") or ""
        end_str = role.get("endDate") or role.get("endSortDate") or ""

        is_current = end_str in ("Present", "present", "9999-12", "", "Current", "current")
        start = _parse_date(start_str)
        end = now if is_current else _parse_date(end_str)

        if not start or not end:
            continue

        months = (end.year - start.year) * 12 + (end.month - start.month)
        total_months += max(0, months)

    years = round(total_months / 12, 1)
    logger.info(f"[scoring] candidate_years={years} from {len(experience)} roles")
    return years


# ── Required years extraction ─────────────────────────────────────────────────

def extract_required_years(description: str) -> tuple[float, float]:
    """
    Parse min and max required years from job description text.
    Returns (min, max). Returns (0, 0) if not found.
    """
    desc = description or ""

    # "6-12 years", "6–12 years", "6 to 12 years"
    m = re.search(r'(\d+)\s*[-–to]+\s*(\d+)\s*years?', desc, re.IGNORECASE)
    if m:
        return float(m.group(1)), float(m.group(2))

    # "6+ years", "6 or more years", "at least 6 years", "minimum 6 years"
    m = re.search(
        r'(?:at\s+least|minimum|min\.?|over|more\s+than)?\s*(\d+)\+?\s*(?:or\s+more)?\s*years?',
        desc, re.IGNORECASE
    )
    if m:
        val = float(m.group(1))
        return val, val + 5

    return 0.0, 0.0


# ── Experience score ──────────────────────────────────────────────────────────

def calc_experience_score(candidate_years: float, min_req: float, max_req: float) -> float | None:
    """
    Hard gap-based formula. Returns None if required years couldn't be extracted
    (caller should let LLM score it instead).
    """
    if min_req == 0 and max_req == 0:
        return None

    gap = min_req - candidate_years

    if gap <= 0:   return 9.5   # meets or exceeds minimum
    if gap <= 1:   return 7.5   # 1 year short — close enough
    if gap <= 2:   return 6.0   # 2 years short
    if gap <= 3:   return 4.5   # 3 years short
    if gap <= 5:   return 3.0   # 4–5 years short
    return 1.5                  # 5+ years short — significant mismatch


# ── Skills score ──────────────────────────────────────────────────────────────

# ── JD keyword extraction for resume tailoring ────────────────────────────────

# Multi-word tech phrases to extract before single-word parsing
_MULTI_WORD_PHRASES = [
    "apache spark", "delta lake", "azure databricks", "apache kafka",
    "apache airflow", "apache flink", "apache beam", "apache hive",
    "dbt core", "great expectations", "aws glue", "aws lambda",
    "aws s3", "aws emr", "aws redshift", "google bigquery", "google cloud",
    "azure data factory", "azure synapse", "power bi", "tableau server",
    "a/b testing", "machine learning", "deep learning", "large language models",
    "data warehouse", "data lakehouse", "data lake", "data mesh",
    "real-time", "near real-time", "event driven", "event sourcing",
    "ci/cd", "github actions", "kubernetes", "docker compose",
    "spark streaming", "structured streaming", "change data capture",
    "slowly changing dimensions", "star schema", "snowflake schema",
]

# Single words that are almost always noise in JDs
_RESUME_STOP_WORDS = {
    "experience", "strong", "good", "knowledge", "understanding", "ability",
    "working", "proven", "solid", "hands", "proficiency", "familiarity",
    "with", "and", "or", "in", "of", "the", "a", "an", "to", "for",
    "our", "we", "you", "your", "their", "this", "that", "will", "must",
    "should", "including", "such", "as", "etc", "eg", "ie", "via",
    "team", "role", "company", "position", "job", "candidate", "applicant",
    "preferred", "required", "qualifications", "responsibilities", "about",
    "using", "use", "build", "design", "develop", "maintain", "support",
    "work", "help", "join", "seek", "looking", "hire", "apply",
    "bachelor", "master", "degree", "education", "university", "college",
    "year", "years", "month", "months", "minimum", "least",
    "environment", "system", "systems", "platform", "platforms", "solution",
    "data", "based", "level", "high", "new", "key", "core", "cross",
    # adjectives that appear capitalised at sentence start — not tech terms
    "expert", "advanced", "deep", "senior", "junior", "lead", "principal",
    "extensive", "excellent", "exceptional", "demonstrated", "significant",
    "effective", "efficient", "scalable", "reliable", "robust", "complex",
    "critical", "relevant", "multiple", "various", "large", "small",
    "highly", "fully", "well", "best", "better", "ideal", "preferred",
}


def extract_jd_must_have_keywords(description: str, candidate_skills: set[str]) -> list[str]:
    """
    Extract the most important tech keywords from a JD that the candidate actually has.
    Returns a ranked list: candidate-matching keywords first, then remaining JD keywords.
    Used to tell the resume builder which terms must appear in the resume.
    """
    desc = description or ""
    desc_lower = desc.lower()

    found = []

    # 1. Multi-word phrases first (highest signal)
    for phrase in _MULTI_WORD_PHRASES:
        if phrase in desc_lower:
            found.append(phrase)

    # 2. Single capitalised / camelCase / known-tech tokens
    tokens = re.findall(r'\b[A-Z][a-zA-Z0-9+#.]*\b|\b[a-z][a-z0-9]*(?:[A-Z][a-z0-9]+)+\b', desc)
    for t in tokens:
        clean = t.strip(".,;:()")
        if len(clean) < 2:
            continue
        lower = clean.lower()
        if lower in _RESUME_STOP_WORDS:
            continue
        if lower not in [f.lower() for f in found]:
            found.append(clean)

    # 3. Words after "experience with/in", "proficiency in", "expertise in"
    skill_phrases = re.findall(
        r'(?:experience with|experience in|proficiency in|expertise in|knowledge of|familiarity with)\s+([A-Za-z0-9+#.,\s/]+?)(?:\.|,|\n|and|or)',
        desc, re.IGNORECASE
    )
    for phrase in skill_phrases:
        for word in phrase.split():
            clean = word.strip(".,;:()/").lower()
            if len(clean) > 2 and clean not in _RESUME_STOP_WORDS:
                if clean not in [f.lower() for f in found]:
                    found.append(word.strip(".,;:()"))

    # Deduplicate preserving order, candidate-matching keywords first
    seen = set()
    candidate_match = []
    jd_only = []
    for kw in found:
        lower = kw.lower()
        if lower in seen:
            continue
        seen.add(lower)
        if lower in candidate_skills:
            candidate_match.append(kw)
        else:
            jd_only.append(kw)

    result = candidate_match + jd_only
    logger.info(f"[scoring] JD keywords: {len(candidate_match)} candidate-matching, {len(jd_only)} JD-only, total={len(result)}")
    return result[:40]  # cap at 40 to keep prompt size sane


def calc_skills_score(gen_content: dict, job_description: str) -> float | None:
    """
    Measures what % of the candidate's skills appear in the job description.
    Falls back to None if candidate has no skills listed.
    """
    skills_data = gen_content.get("skills", {})
    if isinstance(skills_data, list):
        # flat list format
        all_skills = set()
        for group in skills_data:
            for item in (group.get("items") or []):
                all_skills.add(item.lower().strip())
    elif isinstance(skills_data, dict):
        all_skills = set()
        for category in ["languages", "frameworks", "tools", "concepts"]:
            for skill in skills_data.get(category, []):
                all_skills.add(skill.lower().strip())
    else:
        return None

    if not all_skills:
        return None

    jd_lower = (job_description or "").lower()
    matched = sum(1 for skill in all_skills if skill in jd_lower)
    match_rate = matched / len(all_skills)

    logger.info(f"[scoring] skills matched={matched}/{len(all_skills)} rate={match_rate:.2f}")

    if match_rate >= 0.5:  return 9.5
    if match_rate >= 0.35: return 8.0
    if match_rate >= 0.2:  return 6.5
    if match_rate >= 0.1:  return 5.0
    if match_rate >= 0.05: return 3.5
    return 2.0
