from __future__ import annotations

from typing import Any, Dict, List, Optional


FIELD_DESCRIPTIONS: Dict[str, str] = {
    "Background": "Mevcut durum ve problem özeti.",
    "Expected Results": "Beklenen somut sonuçlar ve başarı ölçütü.",
    "Target Customer Group": "Etkilenen müşteri segmenti.",
    "Impacted Channels": "Etkilenen kanallar (app/web/call center/store/API vb.).",
    "Impacted Journey": "Etkilenen journey (mevcut/yeni).",
    "Journeys Description": "As-is ve To-be akış açıklaması; edge-case dahil.",
    "Reports Needed": "İhtiyaç duyulan raporlar / metrikler.",
    "Traffic Forecast": "Beklenen trafik / kullanım tahmini.",
}

# Minimal relevance map: only send a small slice of fields to the LLM
RELATED_FIELDS: Dict[str, List[str]] = {
    "Background": ["Background", "Impacted Journey", "Impacted Channels"],
    "Expected Results": ["Expected Results", "Reports Needed", "Traffic Forecast"],
    "Target Customer Group": ["Target Customer Group", "Impacted Channels", "Impacted Journey"],
    "Impacted Channels": ["Impacted Channels", "Impacted Journey", "Target Customer Group"],
    "Impacted Journey": ["Impacted Journey", "Journeys Description", "Impacted Channels"],
    "Journeys Description": ["Journeys Description", "Impacted Journey", "Impacted Channels"],
    "Reports Needed": ["Reports Needed", "Expected Results"],
    "Traffic Forecast": ["Traffic Forecast", "Impacted Channels", "Impacted Journey"],
}

def build_fields_context(fields: Dict[str, Any], current_field: str, max_chars: int = 1200) -> str:
    keys = RELATED_FIELDS.get(current_field, list(fields.keys()))
    lines = []
    for k in keys:
        v = fields.get(k, "")
        if isinstance(v, list):
            v_str = ", ".join([str(x) for x in v])
        else:
            v_str = str(v)
        v_str = v_str.strip()
        if not v_str:
            continue
        lines.append(f"- {k}: {v_str}")

    text = "\n".join(lines)
    return text[:max_chars]

def build_rag_snippets(snippets: Optional[List[str]], max_snippets: int = 3, max_chars_each: int = 700) -> str:
    if not snippets:
        return ""
    clipped = [s.strip()[:max_chars_each] for s in snippets[:max_snippets] if s and s.strip()]
    if not clipped:
        return ""
    return "\n\n".join([f"[Snippet {i+1}] {c}" for i, c in enumerate(clipped)])

def field_desc(field_name: str) -> str:
    return FIELD_DESCRIPTIONS.get(field_name, "")
