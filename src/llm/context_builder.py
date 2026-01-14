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
    "Privacy / Compliance": "Kişisel veri / KVKK-GDPR / uyumluluk etkisi.",
}

# Minimal relevance map: only send a small slice of fields to the LLM
RELATED_FIELDS: Dict[str, List[str]] = {
    "Background": ["Background", "Impacted Journey", "Impacted Channels", "Target Customer Group"],
    "Expected Results": ["Expected Results", "Reports Needed", "Traffic Forecast"],
    "Target Customer Group": ["Target Customer Group", "Impacted Channels", "Impacted Journey"],
    "Impacted Channels": ["Impacted Channels", "Impacted Journey", "Target Customer Group"],
    "Impacted Journey": ["Impacted Journey", "Journeys Description", "Impacted Channels"],
    "Journeys Description": ["Journeys Description", "Impacted Journey", "Impacted Channels"],
    "Reports Needed": ["Reports Needed", "Expected Results"],
    "Traffic Forecast": ["Traffic Forecast", "Impacted Channels", "Impacted Journey"],
    "Privacy / Compliance": ["Privacy / Compliance", "Background", "Impacted Channels", "Impacted Journey"],
}


def _as_text(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, list):
        return ", ".join([str(x) for x in v if x is not None]).strip()
    return str(v).strip()


def _clip(s: str, n: int) -> str:
    s = (s or "").strip()
    if len(s) <= n:
        return s
    return s[:n].rstrip() + "…"


def build_fields_context(
    fields: Dict[str, Any],
    current_field: str,
    max_chars: int = 1200,
    *,
    max_chars_per_field: int = 420,
) -> str:
    """
    Token-safe: limits BOTH per-field and total characters.
    Keeps only related fields (or all fields if mapping missing).
    """
    if not fields:
        return ""

    keys = RELATED_FIELDS.get(current_field, list(fields.keys()))

    lines: List[str] = []
    used = 0

    for k in keys:
        v_str = _as_text(fields.get(k, ""))
        if not v_str:
            continue

        v_str = _clip(v_str, max_chars_per_field)
        line = f"- {k}: {v_str}"

        # +1 for newline
        if used + len(line) + 1 > max_chars:
            break

        lines.append(line)
        used += len(line) + 1

    return "\n".join(lines).strip()


def build_rag_snippets(
    snippets: Optional[List[str]],
    max_snippets: int = 3,
    max_chars_each: int = 700,
    *,
    max_total_chars: int = 2200,
) -> str:
    """
    Token-safe: limits per snippet AND total characters.
    """
    if not snippets:
        return ""

    out: List[str] = []
    used = 0

    for i, s in enumerate(snippets[:max_snippets], start=1):
        s = (s or "").strip()
        if not s:
            continue

        s = _clip(s, max_chars_each)
        block = f"[Snippet {i}] {s}"

        # +2 for spacing
        if used + len(block) + 2 > max_total_chars:
            break

        out.append(block)
        used += len(block) + 2

    return "\n\n".join(out).strip()


def field_desc(field_name: str) -> str:
    return FIELD_DESCRIPTIONS.get(field_name, "")
