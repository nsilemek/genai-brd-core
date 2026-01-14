from __future__ import annotations

import json
import re
from typing import Any, Dict


class JSONParseError(ValueError):
    pass


def _extract_json_object(text: str) -> str:
    """
    Try to extract the first JSON object from a text response.
    """

    if not text:
        raise JSONParseError("Empty model output")

    # If model wrapped in ```json ... ```
    fenced = re.search(r"```json\s*(\{.*?\})\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        return fenced.group(1)

    # Fallback: extract first top-level {...}
    start = text.find("{")
    if start == -1:
        raise JSONParseError("No '{' found in model output")

    depth = 0
    for i in range(start, len(text)):
        c = text[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]

    raise JSONParseError("Unbalanced JSON braces in model output")


def _sanitize_json(text: str) -> str:
    """
    Fix common LLM JSON mistakes so json.loads can parse it.
    """
    t = text.strip()

    # Python None / True / False → JSON
    t = re.sub(r"\bNone\b", "null", t)
    t = re.sub(r"\bTrue\b", "true", t)
    t = re.sub(r"\bFalse\b", "false", t)

    # .7 → 0.7
    t = re.sub(r":\s*\.(\d+)", r": 0.\1", t)

    # trailing commas before } or ]
    t = re.sub(r",\s*([}\]])", r"\1", t)

    return t


def parse_json_strict(text: str) -> Dict[str, Any]:
    """
    Parse JSON from model output.
    Accepts:
      - pure JSON
      - JSON inside code fences
      - JSON embedded in text

    Also repairs common LLM JSON errors.
    """
    if not text:
        raise JSONParseError("Empty model output")

    # Try direct
    try:
        return json.loads(text)
    except Exception:
        pass

    # Try extracted object
    try:
        extracted = _extract_json_object(text)
        extracted = _sanitize_json(extracted)
        return json.loads(extracted)
    except Exception as e:
        raise JSONParseError(
            f"Failed to parse JSON: {e}\n--- Raw ---\n{text[:800]}"
        )
