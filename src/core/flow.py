from __future__ import annotations

import os
from typing import Any, Dict, Optional

from ..llm.client import LLMClient
from .context_builder import build_fields_context, build_rag_snippets, field_desc

from .state import load_session, save_session, update_field, set_answer
from .mapping import pick_next_field, question_ids_for_field
from ..scoring.scoring_engine_final import (
    compute_scores_from_fields,
    get_weak_fields,
    resolve_questions,
)

# -----------------------------
# LLM Switch (Demo-safe)
"""
ENV CONFIG NOTES
----------------
USE_LLM=0
- LLM calls are disabled
- normalize_answer uses stub logic
- Demo-safe mode (no external dependency)

USE_LLM=1
- LLMClient is used for answer normalization
- If LLM fails, system automatically falls back to stub
- Safe for production/tool integration

PYTHONPATH=.
- Required to resolve src.* imports correctly
"""
# -----------------------------
USE_LLM = os.getenv("USE_LLM", "0") == "1"

_llm = None
def _get_llm() -> LLMClient:
    global _llm
    if _llm is None:
        _llm = LLMClient()
    return _llm


def normalize_answer_stub(field_name: str, user_text: str) -> Dict[str, Any]:
    return {
        "value": user_text.strip(),
        "confidence": 1.0,
        "needs_clarification": False,
        "followup_question": None,
    }


def normalize_answer_llm(field_name: str, user_text: str, fields: dict, rag_snippets=None) -> Dict[str, Any]:
    variables = {
        "field_name": field_name,
        "field_desc": field_desc(field_name),
        "fields_context": build_fields_context(fields, field_name),
        "rag_snippets": build_rag_snippets(rag_snippets),
        "user_answer": user_text.strip(),
    }
    llm = _get_llm()
    return llm.run_json("normalize_answer.txt", variables, max_output_tokens=450)


def normalize_answer(field_name: str, user_text: str, fields: dict, rag_snippets=None) -> Dict[str, Any]:
    """
    Single entry point:
      - USE_LLM=0 => stub
      - USE_LLM=1 => LLM
      - LLM fails => fallback to stub
    """
    if not USE_LLM:
        return normalize_answer_stub(field_name, user_text)

    try:
        return normalize_answer_llm(field_name, user_text, fields, rag_snippets=rag_snippets)
    except Exception:
        # Demo guarantee: never crash the flow because of LLM
        return normalize_answer_stub(field_name, user_text)


# -----------------------------
# Payload builder
# -----------------------------
def _build_bot_payload(
    session_id: str,
    state_fields: Dict[str, Any],
    score_result,
    next_field: Optional[str],
    q_texts: list,
) -> Dict[str, Any]:
    return {
        "session_id": session_id,
        "submit_allowed": score_result.submit_allowed,
        "submit_blockers": score_result.submit_blockers,
        "total_score": score_result.total_score,
        "max_total": score_result.max_total,
        "weak_fields": get_weak_fields(score_result),
        "next_field": next_field,
        "next_questions": q_texts,  # Turkish question texts (or follow-up)
        "fields": state_fields,     # so UI can show preview chips etc.
        "field_scores": [
            {
                "field": fs.field,
                "score": fs.score,
                "max_score": fs.max_score,
                "findings": fs.findings,
                "question_ids": fs.question_ids,
            }
            for fs in score_result.field_scores
        ],
    }


# -----------------------------
# Public entrypoints
# -----------------------------
def start_or_resume(session_id: str, data_dir: str = "data/sessions") -> Dict[str, Any]:
    state = load_session(session_id, data_dir=data_dir)

    score_result = compute_scores_from_fields(state.fields)
    weak = get_weak_fields(score_result)
    next_field = pick_next_field(score_result, state.fields, weak_fields=weak)

    qids = question_ids_for_field(score_result, next_field) if next_field else []
    q_texts = resolve_questions(qids)[:2] if qids else []

    return _build_bot_payload(state.session_id, state.fields, score_result, next_field, q_texts)


def handle_user_message(
    session_id: str,
    user_text: str,
    current_field: str,
    question_id: Optional[str] = None,
    data_dir: str = "data/sessions",
) -> Dict[str, Any]:
    state = load_session(session_id, data_dir=data_dir)

    # 1) store raw answer (optional)
    if question_id:
        set_answer(state, question_id, user_text)

    # 2) normalize answer (LLM or stub)
    # rag_snippets = retrieve_snippets(current_field, state.rag_index_id, vector_store)
    norm = normalize_answer(current_field, user_text, state.fields, rag_snippets=[])

    needs = bool(norm.get("needs_clarification", False))
    followup = norm.get("followup_question")

    # 2b) If clarification needed -> ask follow-up and do NOT update field yet
    if needs and followup:
        # Persist minimal session info so UI can keep continuity
        state.current_field = current_field
        state.last_question_ids = [question_id] if question_id else []
        save_session(state, data_dir=data_dir)

        # Score without changing fields (optional)
        score_result = compute_scores_from_fields(state.fields)
        return _build_bot_payload(
            state.session_id,
            state.fields,
            score_result,
            next_field=current_field,
            q_texts=[str(followup)],
        )

    value = norm.get("value", "").strip()
    confidence = float(norm.get("confidence", 1.0))

    # 3) update canonical field value + audit log
    update_field(
        state,
        field_name=current_field,
        value=value,
        source="guided",
        confidence=confidence,
        evidence=f"User answer to {question_id}" if question_id else "User answer",
    )

    # 4) scoring
    score_result = compute_scores_from_fields(state.fields)
    weak = get_weak_fields(score_result)

    # 5) pick next field
    next_field = pick_next_field(score_result, state.fields, weak_fields=weak)

    # 6) next questions from scoring engine
    qids = question_ids_for_field(score_result, next_field) if next_field else []
    q_texts = resolve_questions(qids)[:2] if qids else []

    # 7) persist session
    state.current_field = next_field
    state.last_question_ids = qids[:2]
    state.scores = {
        "total_score": score_result.total_score,
        "max_total": score_result.max_total,
        "submit_allowed": score_result.submit_allowed,
        "submit_blockers": score_result.submit_blockers,
        "weak_fields": weak,
    }
    save_session(state, data_dir=data_dir)

    return _build_bot_payload(state.session_id, state.fields, score_result, next_field, q_texts)
