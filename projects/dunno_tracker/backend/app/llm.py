"""
LLM provider auto-detection.
Reads which API key is set in env and returns the right analyzer.
Priority: ANTHROPIC_API_KEY > OPENAI_API_KEY > DEEPSEEK_API_KEY > GEMINI_API_KEY
"""
from __future__ import annotations
import json
import os
import re
from typing import Any


ANALYSIS_PROMPT = """You are analyzing a conversation between a user and an AI assistant.

RULES:
1. Intents must cover the whole conversation and weights must sum to 1.0
2. Use EXACT names from the intent library if the concept matches — same concept = same name always
3. New intent names: snake_case, 2-3 words, specific not generic (e.g. "investment_advice" not "information")
4. Group related messages — don't create one intent per message
5. Corrections: only flag explicit user pushback on AI's response (not normal conversation)
6. Summary: 5-6 sentences covering what user wanted, what happened, whether resolved

INTENT LIBRARY (use exact name if concept matches):
{library}

CONVERSATION ({n} messages, 0-indexed):
{messages}

Return ONLY valid JSON, no markdown, no extra text:
{{
  "summary": "5-6 sentence summary",
  "intents": [
    {{
      "name": "snake_case_name",
      "display_name": "Human Readable Name",
      "msg_start": 0,
      "msg_end": 3,
      "weight": 0.4,
      "is_new": false
    }}
  ],
  "corrections": [
    {{
      "msg_index": 5,
      "reason": "user corrected X to Y"
    }}
  ],
  "resolution": {{
    "resolved": true,
    "type": "success",
    "reason": "user expressed satisfaction"
  }}
}}"""


def _extract_json(text: str) -> dict:
    """Extract JSON from LLM response, handling markdown code blocks."""
    text = text.strip()
    # Strip markdown code blocks
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def _build_prompt(messages: list[dict], intent_library: list[dict]) -> str:
    lib_text = "\n".join(
        f"- {e['name']}: {e.get('display_name', '')} — {e.get('description') or 'no description'}"
        for e in intent_library
    ) or "(empty — this is the first session being analyzed)"

    msgs_text = "\n".join(
        f"[{i}] {m['role'].upper()}: {(m.get('content') or '')[:400]}"
        for i, m in enumerate(messages)
    )

    return ANALYSIS_PROMPT.format(
        library=lib_text,
        n=len(messages),
        messages=msgs_text,
    )


class _AnthropicAnalyzer:
    def __init__(self, api_key: str) -> None:
        from anthropic import Anthropic
        self._client = Anthropic(api_key=api_key)

    def analyze(self, messages: list[dict], intent_library: list[dict]) -> dict:
        prompt = _build_prompt(messages, intent_library)
        resp = self._client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )
        return _extract_json(resp.content[0].text)


class _OpenAIAnalyzer:
    def __init__(self, api_key: str, base_url: str | None = None) -> None:
        from openai import OpenAI
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._model = "gpt-4o-mini" if not base_url else "deepseek-chat"

    def analyze(self, messages: list[dict], intent_library: list[dict]) -> dict:
        prompt = _build_prompt(messages, intent_library)
        resp = self._client.chat.completions.create(
            model=self._model,
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1500,
        )
        return json.loads(resp.choices[0].message.content)


class _GeminiAnalyzer:
    def __init__(self, api_key: str) -> None:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        self._model = genai.GenerativeModel("gemini-1.5-flash")

    def analyze(self, messages: list[dict], intent_library: list[dict]) -> dict:
        prompt = _build_prompt(messages, intent_library)
        resp = self._model.generate_content(prompt)
        return _extract_json(resp.text)


_analyzer: Any = None


def get_analyzer() -> Any | None:
    """Returns the configured LLM analyzer or None if no key is set."""
    global _analyzer
    if _analyzer is not None:
        return _analyzer

    if os.getenv("ANTHROPIC_API_KEY"):
        _analyzer = _AnthropicAnalyzer(os.environ["ANTHROPIC_API_KEY"])
    elif os.getenv("OPENAI_API_KEY"):
        _analyzer = _OpenAIAnalyzer(os.environ["OPENAI_API_KEY"])
    elif os.getenv("DEEPSEEK_API_KEY"):
        _analyzer = _OpenAIAnalyzer(
            api_key=os.environ["DEEPSEEK_API_KEY"],
            base_url="https://api.deepseek.com",
        )
    elif os.getenv("GEMINI_API_KEY"):
        _analyzer = _GeminiAnalyzer(os.environ["GEMINI_API_KEY"])

    return _analyzer
