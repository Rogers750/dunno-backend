"""
Session analysis pipeline.
Uses LLM if a key is configured, falls back to pattern matching.
Triggered debounced: skips if analyzed within last 30 seconds.
"""
from __future__ import annotations
import re
from datetime import datetime, timezone


# ── Fallback pattern classifier (used when no LLM key is set) ──────────────

_INTENT_PATTERNS: list[tuple[str, list[str]]] = [
    ("request_fix",        [r"\bfix\b", r"\bdebug\b", r"\berror\b", r"\bbroken\b", r"\bnot working\b", r"\bbug\b"]),
    ("request_generation", [r"\bwrite\b", r"\bgenerate\b", r"\bcreate\b", r"\bdraft\b", r"\bcompose\b"]),
    ("request_summary",    [r"\bsummariz\b", r"\bsummary\b", r"\btldr\b", r"\boverview\b"]),
    ("request_analysis",   [r"\banalyz\b", r"\breview\b", r"\bevaluat\b", r"\bassess\b"]),
    ("request_comparison", [r"\bcompare\b", r"\bdifference between\b", r"\bversus\b"]),
    ("request_help",       [r"\bhelp me\b", r"\bhow do i\b", r"\bhow to\b"]),
    ("get_information",    [r"\bwhat is\b", r"\bexplain\b", r"\btell me\b", r"\bwho is\b", r"\bwhy\b"]),
]

_CORRECTION_PATTERNS = [
    r"^no[,\.!\s]", r"\bthat.s wrong\b", r"\bi meant\b",
    r"\bactually[,\s]", r"\bwait[,\s]", r"\byou misunderstood\b", r"\bnope\b",
]

_RESOLUTION_POSITIVE = [r"\bthank you\b", r"\bthanks\b", r"\bthat works\b", r"\bperfect\b", r"\bgot it\b", r"\bsolved\b"]
_RESOLUTION_NEGATIVE = [r"\bforget it\b", r"\bnever mind\b", r"\buseless\b", r"\bnot helpful\b"]


def _match(text: str, patterns: list[str]) -> bool:
    t = text.lower().strip()
    return any(re.search(p, t) for p in patterns)


def _fallback_analysis(messages: list[dict]) -> dict:
    """Pattern-based analysis when no LLM is available."""
    user_msgs = [m for m in messages if m["role"] == "user" and m.get("content")]

    # Intents
    intents: list[dict] = []
    for m in user_msgs:
        for name, patterns in _INTENT_PATTERNS:
            if _match(m["content"], patterns):
                if not intents or intents[-1]["name"] != name:
                    intents.append({"name": name, "display_name": name.replace("_", " ").title(), "weight": 0.0, "msg_start": 0, "msg_end": 0, "is_new": True})
                break

    # Normalize weights
    if intents:
        w = round(1.0 / len(intents), 3)
        for intent in intents:
            intent["weight"] = w

    # Corrections
    corrections = []
    for i, m in enumerate(messages):
        if m["role"] == "user" and m.get("content") and i > 0 and messages[i - 1]["role"] == "assistant":
            if _match(m["content"], _CORRECTION_PATTERNS):
                corrections.append({"msg_index": i, "reason": "user pushback detected"})

    # Resolution
    resolved, res_type = False, "abandoned"
    for m in messages[-4:]:
        if m.get("content"):
            if _match(m["content"], _RESOLUTION_POSITIVE):
                resolved, res_type = True, "success"
                break
            if _match(m["content"], _RESOLUTION_NEGATIVE):
                break

    return {
        "summary": None,
        "intents": intents,
        "corrections": corrections,
        "resolution": {"resolved": resolved, "type": res_type, "reason": None},
    }


# ── Deduplicate cumulative message history ──────────────────────────────────

def _deduplicate(messages: list[dict]) -> list[dict]:
    seen: set[tuple[str, str]] = set()
    result = []
    for m in messages:
        key = (m["role"], (m.get("content") or "")[:300])
        if key not in seen:
            seen.add(key)
            result.append(m)
    return result


# ── Main entry point ────────────────────────────────────────────────────────

def analyze_session(repo, session_db_id: str) -> None:
    """
    Analyze a session using LLM (or fallback to patterns).
    Skips if session was analyzed in the last 30 seconds.
    """
    # Debounce: skip if recently analyzed
    session_meta = repo.get_session_meta(session_db_id)
    if session_meta:
        last = session_meta.get("last_analyzed_at")
        if last:
            if isinstance(last, str):
                last = datetime.fromisoformat(last.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            if (now - last).total_seconds() < 30:
                return

    # Get messages
    events = repo.get_session_events_with_messages(session_db_id)
    if not events:
        return

    event_ids = [str(e["id"]) for e in events]
    raw_messages = repo.get_messages_for_events(event_ids)
    messages = _deduplicate(raw_messages)

    user_turns = [m for m in messages if m["role"] == "user" and m.get("content")]
    if len(user_turns) < 1:
        return

    # Get project_id from session for intent library lookup
    agent_id = session_meta.get("agent_id") if session_meta else None
    project_id = session_meta.get("project_id") if session_meta else None

    # Get existing intent library
    intent_library = repo.get_intent_library(project_id) if project_id else []

    # Run LLM or fallback
    from app.llm import get_analyzer
    analyzer = get_analyzer()

    if analyzer:
        try:
            result = analyzer.analyze(messages, intent_library)
        except Exception as e:
            print(f"[analysis] LLM failed ({e}), falling back to patterns")
            result = _fallback_analysis(messages)
    else:
        result = _fallback_analysis(messages)

    # Upsert intent library entries and collect library_ids
    intents_to_store = []
    for intent in (result.get("intents") or []):
        name = intent.get("name", "").strip()
        if not name:
            continue
        display = intent.get("display_name") or name.replace("_", " ").title()
        lib_entry = repo.upsert_intent_library(project_id, name, display)
        lib_id = lib_entry["id"] if lib_entry else None
        intents_to_store.append({
            "session_id": session_db_id,
            "library_id": lib_id,
            "agent_id": agent_id,
            "intent": name,
            "display_name": display,
            "weight": intent.get("weight", 0),
            "msg_start": intent.get("msg_start", 0),
            "msg_end": intent.get("msg_end", 0),
        })

    corrections_to_store = [
        {"session_id": session_db_id, "msg_index": c.get("msg_index"), "reason": c.get("reason")}
        for c in (result.get("corrections") or [])
    ]

    resolution = result.get("resolution") or {}
    resolution_to_store = {
        "session_id": session_db_id,
        "resolved": resolution.get("resolved", False),
        "resolution_type": resolution.get("type", "abandoned"),
        "summary": resolution.get("reason"),
    }

    summary = result.get("summary")

    repo.replace_session_analysis(session_db_id, intents_to_store, corrections_to_store, resolution_to_store)
    repo.update_session_analysis_meta(session_db_id, summary)
