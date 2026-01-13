from __future__ import annotations

from typing import List, Optional

from ..scoring.scoring_engine_final import ScoreResult
from .constants import BRD_FIELDS  # canonical order

PRIVACY_FIELD = "Privacy / Compliance"
PRIVACY_QIDS = ["Q_PRIVACY_MIN"]

# Eğer BRD_FIELDS içinde Background yoksa/ farklı isimse, burayı senin gerçek field adınla eşleştir.
BACKGROUND_FIELD = "Background"


def _is_empty(v) -> bool:
    return (v is None) or (isinstance(v, str) and v.strip() == "")


def _build_field_order() -> List[str]:
    """
    En kritik: field sırası deterministik olmalı.
    - Background her zaman ilk.
    - Privacy her zaman en son.
    - Diğerleri BRD_FIELDS sırasıyla.
    """
    base = list(BRD_FIELDS)

    # Remove privacy if exists; we'll append at end
    base = [f for f in base if f != PRIVACY_FIELD]

    # Ensure Background is first (if exists)
    if BACKGROUND_FIELD in base:
        base.remove(BACKGROUND_FIELD)
        base = [BACKGROUND_FIELD] + base

    # Privacy last (if exists in BRD_FIELDS)
    if PRIVACY_FIELD in BRD_FIELDS:
        base.append(PRIVACY_FIELD)

    return base


FIELD_ORDER = _build_field_order()


def pick_next_field(
    result: ScoreResult,
    fields: dict,
    weak_fields: Optional[List[str]] = None,
) -> Optional[str]:
    """
    Priority order (Privacy LAST):
    1) weak_fields (if provided) — excluding privacy
       - Not only empty; if a field is weak, ask it even if partially filled.
    2) any field with score == 0 — excluding privacy
    3) first empty field in FIELD_ORDER — excluding privacy
    4) if all non-privacy fields are filled => Privacy (if empty)
    """

    # 1) Weak fields first (skip privacy). Ask even if partially filled.
    if weak_fields:
        for f in weak_fields:
            if f == PRIVACY_FIELD:
                continue
            if f in fields:
                return f

    # 2) Score==0 fields first (critical gaps) (skip privacy)
    for fs in result.field_scores:
        if fs.field == PRIVACY_FIELD:
            continue
        if fs.field in fields and fs.score == 0:
            return fs.field

    # 3) Otherwise first empty non-privacy field (deterministic FIELD_ORDER)
    for k in FIELD_ORDER:
        if k == PRIVACY_FIELD:
            continue
        if k in fields and _is_empty(fields.get(k)):
            return k

    # 4) All non-privacy fields filled -> ask privacy last (if empty)
    if PRIVACY_FIELD in fields and _is_empty(fields.get(PRIVACY_FIELD, "")):
        return PRIVACY_FIELD

    return None


def question_ids_for_field(result: ScoreResult, field_name: str) -> List[str]:
    # Privacy hard-map (even if scoring engine doesn't return it)
    if field_name == PRIVACY_FIELD:
        return PRIVACY_QIDS

    # Default: based on scoring engine suggestions
    for fs in result.field_scores:
        if fs.field == field_name:
            return fs.question_ids or []
    return []


def best_question_id(question_ids: List[str]) -> Optional[str]:
    return question_ids[0] if question_ids else None
