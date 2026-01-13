from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..llm.context_builder import build_rag_snippets
from ..llm.client import LLMClient
from .config import USE_LLM


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


def _template_section(section_name: str, fields: Dict[str, Any]) -> str:
    """
    Deterministic preview used when USE_LLM=0.
    Goal: Always produce a nice-looking BRD preview for demo.
    """
    if section_name == "Background":
        bg = (fields.get("Background") or "").strip()
        tgt = (fields.get("Target Customer Group") or "").strip()
        return (
            f"## Background\n"
            f"{bg if bg else '(Background missing)'}\n\n"
            f"**Target Customer Group:** {tgt if tgt else '(missing)'}"
        ).strip()

    if section_name == "Impacts":
        ch = (fields.get("Impacted Channels") or "").strip()
        j = (fields.get("Impacted Journey") or "").strip()
        return (
            f"## Impacts\n"
            f"**Impacted Channels:** {ch if ch else '(missing)'}\n"
            f"**Impacted Journey:** {j if j else '(missing)'}"
        ).strip()

    if section_name == "Journey Description":
        jd = (fields.get("Journeys Description") or "").strip()
        return (
            f"## Journey Description\n"
            f"{jd if jd else '(Journeys Description missing)'}"
        ).strip()

    if section_name == "Expected Results":
        er = (fields.get("Expected Results") or "").strip()
        rep = (fields.get("Reports Needed") or "").strip()
        tf = (fields.get("Traffic Forecast") or "").strip()
        return (
            f"## Expected Results\n"
            f"{er if er else '(Expected Results missing)'}\n\n"
            f"**Reports Needed:** {rep if rep else '(missing)'}\n"
            f"**Traffic Forecast:** {tf if tf else '(missing)'}"
        ).strip()

    # fallback
    keys = SECTION_MAP.get(section_name, [])
    return f"## {section_name}\n{_format_section_fields(fields, keys)}"


class BRDGenerator:
    def __init__(self, llm: Optional[LLMClient] = None):
        self.llm = llm or LLMClient()

    def generate_section(
        self,
        section_name: str,
        fields: Dict[str, Any],
        rag_snippets: Optional[List[str]] = None,
    ) -> str:
        # Demo-safe: no LLM calls when USE_LLM=0
        if not USE_LLM:
            return _template_section(section_name, fields)

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
