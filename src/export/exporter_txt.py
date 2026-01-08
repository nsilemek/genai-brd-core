from __future__ import annotations

import os
from typing import Any, Dict, Optional


def render_txt(fields: Dict[str, Any], scores: Optional[Dict[str, Any]] = None) -> str:
    lines = []
    lines.append("TO-BE JOURNEY / BRD OUTPUT")
    lines.append("=" * 28)
    lines.append("")

    # Fields (order matters)
    order = [
        "Background",
        "Expected Results",
        "Target Customer Group",
        "Impacted Channels",
        "Impacted Journey",
        "Journeys Description",
        "Reports Needed",
        "Traffic Forecast",
    ]

    for k in order:
        v = fields.get(k, "")
        lines.append(f"{k}:")
        if isinstance(v, list):
            if v:
                for item in v:
                    lines.append(f" - {item}")
            else:
                lines.append(" (empty)")
        else:
            v_str = str(v).strip()
            lines.append(v_str if v_str else "(empty)")
        lines.append("")

    # Scores (optional)
    if scores:
        lines.append("SCORE SUMMARY")
        lines.append("-" * 12)
        lines.append(f"Total Score: {scores.get('total_score')} / {scores.get('max_total')}")
        lines.append(f"Submit Allowed: {scores.get('submit_allowed')}")
        blockers = scores.get("submit_blockers") or []
        if blockers:
            lines.append("Blockers:")
            for b in blockers:
                lines.append(f" - {b}")
        lines.append("")

    return "\n".join(lines)


def export_txt_file(
    out_dir: str,
    session_id: str,
    fields: Dict[str, Any],
    scores: Optional[Dict[str, Any]] = None,
    filename: Optional[str] = None,
) -> str:
    os.makedirs(out_dir, exist_ok=True)
    if not filename:
        filename = f"brd_{session_id}.txt"
    path = os.path.join(out_dir, filename)

    content = render_txt(fields, scores=scores)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    return path
