import re
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


# ── Date parsing ──────────────────────────────────────────────────────────────

def _parse_date(s: str) -> datetime | None:
    if not s:
        return None
    s = s.strip()
    for fmt in ("%Y-%m", "%b %Y", "%B %Y", "%Y", "%m/%Y", "%Y-%m-%d", "%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    logger.warning(f"[scoring] unparseable date: {s!r}")
    return None


# ── Candidate experience ──────────────────────────────────────────────────────

def _parse_duration_string(duration: str) -> float:
    """
    Parse a plain duration string into years.
    Handles: "3.5 years", "2 years 3 months", "1 yr 6 mo", "18 months", "Jan 2021 - Present"
    """
    if not duration:
        return 0.0
    d = duration.strip()

    # Date range: "Jan 2021 - Present" or "2020 - 2023"
    range_match = re.search(r'(.+?)\s*[-–]\s*(.+)', d)
    if range_match:
        start = _parse_date(range_match.group(1).strip())
        end_str = range_match.group(2).strip()
        now = datetime.now()
        is_current = end_str.lower() in ("present", "current", "now", "")
        end = now if is_current else _parse_date(end_str)
        if start and end:
            months = (end.year - start.year) * 12 + (end.month - start.month)
            return round(max(0, months) / 12, 1)

    # Plain duration: "2 years 3 months", "18 months", "3.5 years"
    years = 0.0
    m = re.search(r'(\d+\.?\d*)\s*(?:years?|yrs?)', d, re.IGNORECASE)
    if m:
        years += float(m.group(1))
    m = re.search(r'(\d+)\s*(?:months?|mos?)', d, re.IGNORECASE)
    if m:
        years += float(m.group(1)) / 12
    return round(years, 1)


def extract_candidate_years(gen_content: dict) -> float:
    """Sum experience durations from gen_content. Returns total years as float."""
    # Fast path — pre-computed field
    total = gen_content.get("total_years_experience")
    if total and float(total) > 0:
        logger.info(f"[scoring] candidate_years={total} from total_years_experience field")
        return float(total)

    experience = gen_content.get("experience", [])
    if not experience:
        return 0.0

    now = datetime.now()
    total_months = 0

    if experience:
        logger.info(f"[scoring] first experience entry keys: {list(experience[0].keys())}")

    for role in experience:
        start_str = role.get("startDate") or role.get("sortDate") or ""
        end_str = role.get("endDate") or role.get("endSortDate") or ""

        # If no start/end dates, try parsing the duration field directly
        if not start_str:
            duration_str = role.get("duration") or ""
            if duration_str:
                years = _parse_duration_string(duration_str)
                total_months += int(years * 12)
            continue

        is_current = end_str in ("Present", "present", "9999-12", "", "Current", "current")
        start = _parse_date(start_str)
        end = now if is_current else _parse_date(end_str)

        if not start or not end:
            # Last resort: try duration field
            duration_str = role.get("duration") or ""
            if duration_str:
                years = _parse_duration_string(duration_str)
                total_months += int(years * 12)
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

