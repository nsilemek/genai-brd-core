from __future__ import annotations

from typing import Any, Dict, List, Optional

from .context_builder import build_rag_snippets
from ..llm.client import LLMClient


# Section -> which fields it uses
SECTION_MAP: Dict[str, List[str]] = {
    "Background": ["Background", "Target Customer Group"],
    "Impacts": ["Impacted Channels", "Impacted Journey"],
    "Journey Description": ["Journeys Description"],
    "Expected Results": ["Expected Results", "Reports Needed", "Traffic Forecast"],
}


def _format_section_fields(fields: Dict[str, Any], keys: List[str], max_chars: int = 1800) -> str:
    lines = []
    for k in keys:
        v = fields.get(k, "")
        if isinstance(v, list):
            v_str = ", ".join([str(x) for x in v])
        else:
            v_str = str(v or "")
        v_str = v_str.strip()
        lines.append(f"- {k}: {v_str if v_str else '(empty)'}")
    text = "\n".join(lines)
    return text[:max_chars]


class BRDGenerator:
    def __init__(self, llm: Optional[LLMClient] = None):
        self.llm = llm or LLMClient()

    def generate_section(
        self,
        section_name: str,
        fields: Dict[str, Any],
        rag_snippets: Optional[List[str]] = None,
    ) -> str:
        keys = SECTION_MAP.get(section_name, [])
        section_fields = _format_section_fields(fields, keys)

        variables = {
            "section_name": section_name,
            "section_fields": section_fields,
            "rag_snippets": build_rag_snippets(rag_snippets),
        }
        return self.llm.run_text("generate_section.txt", variables, max_output_tokens=900)

    def generate_preview(
        self,
        fields: Dict[str, Any],
        rag_snippets_by_section: Optional[Dict[str, List[str]]] = None,
    ) -> Dict[str, str]:
        """
        Returns dict: section_name -> text
        """
        out: Dict[str, str] = {}
        for section_name in SECTION_MAP.keys():
            snippets = (rag_snippets_by_section or {}).get(section_name, [])
            out[section_name] = self.generate_section(section_name, fields, snippets)
        return out
