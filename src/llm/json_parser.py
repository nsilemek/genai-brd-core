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
    # If model wrapped in ```json ... ```
    fenced = re.search(r"```json\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if fenced:
        return fenced.group(1)

    # Otherwise find first {...}
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]

    raise JSONParseError("No JSON object found in model output.")


def parse_json_strict(text: str) -> Dict[str, Any]:
    """
    Parse JSON. Accepts:
    - pure JSON
    - JSON inside code fences
    - JSON embedded in text (extract first object)
    """
    try:
        return json.loads(text)
    except Exception:
        pass

    try:
        extracted = _extract_json_object(text)
        return json.loads(extracted)
    except Exception as e:
        raise JSONParseError(f"Failed to parse JSON: {e}\nRaw:\n{text[:800]}")
