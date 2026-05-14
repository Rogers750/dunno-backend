import os
import json
import logging
import httpx

logger = logging.getLogger(__name__)

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"


async def find_element(elements: list[dict], instruction: str) -> dict:
    """
    Given a list of DOM elements and a plain-English instruction,
    returns the index of the element to interact with.

    elements: [{"index": 0, "tag": "button", "text": "Easy Apply", "aria": "..."}]
    instruction: "click the Easy Apply button"
    returns: {"index": 14, "found": True}
    """
    if not elements:
        return {"index": -1, "found": False}

    elements_text = "\n".join(
        f"[{el['index']}] <{el['tag']}> text=\"{el.get('text', '')}\" aria=\"{el.get('aria', '')}\""
        for el in elements
    )

    system = (
        "You are a browser automation agent. Given a list of DOM elements and an instruction, "
        "return the index of the single best matching element.\n"
        "Respond with ONLY a JSON object: {\"index\": <number>, \"found\": <true|false>}\n"
        "If no element matches, return {\"index\": -1, \"found\": false}."
    )

    user = (
        f"INSTRUCTION: {instruction}\n\n"
        f"ELEMENTS:\n{elements_text}"
    )

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{DEEPSEEK_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "response_format": {"type": "json_object"},
            },
        )
        response.raise_for_status()
        data = response.json()

    content = data["choices"][0]["message"]["content"]
    result = json.loads(content)

    index = int(result.get("index", -1))
    found = bool(result.get("found", False)) and index >= 0

    logger.info(f"[extension/crew] instruction={instruction!r} → index={index} found={found}")
    return {"index": index, "found": found}
