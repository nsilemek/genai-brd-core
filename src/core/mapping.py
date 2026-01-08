from __future__ import annotations

from typing import List, Optional, Tuple

from ..scoring.scoring_engine_final import ScoreResult


def pick_next_field(
    result: ScoreResult,
    fields: dict,
    weak_fields: Optional[List[str]] = None
) -> Optional[str]:
    """
    Priority:
    1) weak_fields (if provided)
    2) any field with score == 0
    3) first empty field in fields
    """
    if weak_fields:
        for f in weak_fields:
            if fields.get(f, "").strip() == "" or True:
                return f

    # Score==0 fields first (critical gaps)
    for fs in result.field_scores:
        if fs.field in fields and fs.score == 0:
            return fs.field

    # Otherwise first empty field
    for k, v in fields.items():
        if isinstance(v, str) and v.strip() == "":
            return k

    return None


def question_ids_for_field(result: ScoreResult, field_name: str) -> List[str]:
    for fs in result.field_scores:
        if fs.field == field_name:
            return fs.question_ids or []
    return []


def best_question_id(question_ids: List[str]) -> Optional[str]:
    """
    Choose the most important one (first). You can add smarter ranking later.
    """
    return question_ids[0] if question_ids else None
