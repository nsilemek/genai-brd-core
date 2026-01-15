from __future__ import annotations

import re
from typing import Any, Dict, Optional

from ..rag.retriever import retrieve_snippets_for_flow

from ..llm.client import LLMClient
from ..llm.context_builder import build_fields_context, build_rag_snippets, field_desc
from .config import use_llm  # ✅ runtime read (NOT import-time snapshot)

from .state import (
    load_session,
    save_session,
    update_field,
    set_answer,
    attach_uploaded_file,
)
from .mapping import pick_next_field, question_ids_for_field
from ..scoring.scoring_engine_final import (
    compute_scores_from_fields,
    get_weak_fields,
    resolve_questions,
)

# -----------------------------
# LLM Switch (Demo-safe)
# -----------------------------
_llm: Optional[LLMClient] = None


def _get_llm() -> LLMClient:
    global _llm
    if _llm is None:
        _llm = LLMClient()
    return _llm


# -----------------------------
# Intake (PDF) - constants
# -----------------------------
INTAKE_FIELD = "__INTAKE__"
UPLOAD_PDF_FIELD = "__UPLOAD_PDF__"

PDF_INTRO_Q = (
    "Hazır bir **slayt sunumunuz** var mı?\n\n"
    "- Varsa **Evet** yazın, ardından PDF yükleyin. Ben de önemli noktaları çıkarıp **Background** alanını kısaca doldurayım.\n"
    "- Yoksa **Hayır** yazıp devam edebilirsiniz."
)

PDF_UPLOAD_Q = (
    "PDF dosyanızı şimdi yükleyin. Yükledikten sonra ben özetleyip **Background** alanına ekleyeceğim.\n\n"
    "PDF yoksa **Hayır** yazıp devam edebilirsiniz."
)

INTRO_TEXT = (
    "Merhaba! Ben **V-RAI** 👋 Vodafone için hazırlanmış bir **BRD (Business Requirements Document)** asistanıyım.\n"
    "Sana adım adım sorular sorarak BRD’yi hızlı ve net şekilde doldurmana yardımcı olacağım.\n"
)


# -----------------------------
# Yes/No parsing (robust)
# -----------------------------
def _first_token(text: str) -> str:
    t = (text or "").strip().lower()
    t = re.sub(r"[^\w\sçğıöşü]", " ", t, flags=re.UNICODE)
    t = re.sub(r"\s+", " ", t).strip()
    return t.split(" ")[0] if t else ""


def _is_no(text: str) -> bool:
    return _first_token(text) in {"hayır", "hayir", "yok", "no", "n"}


def _is_yes(text: str) -> bool:
    return _first_token(text) in {"evet", "yes", "var", "y", "ok"}


def _reset_wizard_cursor(state) -> None:
    """Gate geçişlerinde wizard'ın 'hangi alandayım' imlecini temizle."""
    state.current_field = None
    state.last_question_ids = []


# -----------------------------
# Normalization (stub + LLM)
# -----------------------------
def normalize_answer_stub(field_name: str, user_text: str) -> Dict[str, Any]:
    return {
        "value": (user_text or "").strip(),
        "confidence": 0.7,
        "needs_clarification": False,
        "followup_question": None,
    }


def normalize_answer_llm(
    field_name: str,
    user_text: str,
    fields: dict,
    rag_snippets=None,
) -> Dict[str, Any]:
    variables = {
        "field_name": field_name,
        "field_desc": field_desc(field_name),
        "fields_context": build_fields_context(fields, field_name),
        "rag_snippets": build_rag_snippets(rag_snippets),
        "user_answer": (user_text or "").strip(),
    }
    llm = _get_llm()
    return llm.run_json("normalize_answer.txt", variables, max_output_tokens=450)


def normalize_answer(
    field_name: str,
    user_text: str,
    fields: dict,
    rag_snippets=None,
) -> Dict[str, Any]:
    # ✅ IMPORTANT: runtime flag (Streamlit reload + env changes work)
    if not use_llm():
        return normalize_answer_stub(field_name, user_text)

    try:
        return normalize_answer_llm(field_name, user_text, fields, rag_snippets=rag_snippets)
    except Exception:
        # demo-safe fallback
        return normalize_answer_stub(field_name, user_text)


# -----------------------------
# PDF -> Background summarization (LLM)
# -----------------------------
def summarize_pdf_to_background(pdf_text: str, fields: Dict[str, Any]) -> str:
    """
    PDF text'inden Background paragrafı üretir.
    NOT: src/llm/prompts/pdf_to_background.txt dosyanız olmalı.
    """
    # ✅ runtime flag
    if not use_llm():
        return ""

    llm = _get_llm()
    variables = {
        "fields_context": build_fields_context(fields, "Background"),
        "pdf_text": (pdf_text or "")[:12000],
    }
    return llm.run_text("pdf_to_background.txt", variables, max_output_tokens=650)


def _append_background(existing: str, addition: str) -> str:
    existing = (existing or "").strip()
    addition = (addition or "").strip()
    if not addition:
        return existing
    if not existing:
        return addition
    return existing + "\n\n" + addition


# -----------------------------
# Payload builder
# -----------------------------
def _build_bot_payload(
    state,
    score_result,
    next_field: Optional[str],
    q_texts: list,
    *,
    expect_pdf_upload: bool = False,
) -> Dict[str, Any]:
    return {
        "session_id": state.session_id,
        "submit_allowed": score_result.submit_allowed,
        "submit_blockers": score_result.submit_blockers,
        "total_score": score_result.total_score,
        "max_total": score_result.max_total,
        "weak_fields": get_weak_fields(score_result),
        "next_field": next_field,
        "next_questions": q_texts,
        "expect_pdf_upload": expect_pdf_upload,
        "fields": state.fields,
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
        # debug/info
        "pdf_gate_done": getattr(state, "pdf_gate_done", False),
        "pdf_uploaded_path": getattr(state, "pdf_uploaded_path", None),
        "pdf_summary": getattr(state, "pdf_summary", ""),
        "pdf_applied_to_background": getattr(state, "pdf_applied_to_background", False),
        "privacy_ruleset_output": getattr(state, "privacy_ruleset_output", None),
        # RAG debug (opsiyonel)
        "rag_index_id": getattr(state, "rag_index_id", None),
        # LLM debug (opsiyonel)
        "use_llm": bool(use_llm()),
    }


# -----------------------------
# Public entrypoints
# -----------------------------
def start_or_resume(session_id: str, data_dir: str = "data/sessions") -> Dict[str, Any]:
    state = load_session(session_id, data_dir=data_dir)

    # ✅ 0) PDF intake gate (her şeyden önce)
    if not getattr(state, "pdf_gate_done", False):
        score_result = compute_scores_from_fields(state.fields)

        # Gate ekranına girdik -> imleci intake'a set et (stabil)
        state.current_field = INTAKE_FIELD
        state.last_question_ids = []
        save_session(state, data_dir=data_dir)

        return _build_bot_payload(
            state,
            score_result,
            next_field=INTAKE_FIELD,
            q_texts=[PDF_INTRO_Q],
            expect_pdf_upload=False,
        )

    # ✅ normal akış
    score_result = compute_scores_from_fields(state.fields)
    weak = get_weak_fields(score_result)

    next_field = pick_next_field(score_result, state.fields, weak_fields=weak)

    qids = question_ids_for_field(score_result, next_field) if next_field else []
    q_texts = resolve_questions(qids)[:2] if qids else []

    # Persist cursor for stability
    state.current_field = next_field
    state.last_question_ids = qids[:2]
    save_session(state, data_dir=data_dir)

    return _build_bot_payload(state, score_result, next_field, q_texts)


def handle_user_message(
    session_id: str,
    user_text: str,
    current_field: str,
    question_id: Optional[str] = None,
    data_dir: str = "data/sessions",
) -> Dict[str, Any]:
    state = load_session(session_id, data_dir=data_dir)

    # ✅ Intake step
    if current_field == INTAKE_FIELD:
        if _is_no(user_text):
            state.pdf_gate_done = True
            _reset_wizard_cursor(state)  # 👈 kritik
            save_session(state, data_dir=data_dir)
            return start_or_resume(session_id, data_dir=data_dir)

        if _is_yes(user_text):
            score_result = compute_scores_from_fields(state.fields)
            state.current_field = UPLOAD_PDF_FIELD
            state.last_question_ids = []
            save_session(state, data_dir=data_dir)
            return _build_bot_payload(
                state,
                score_result,
                next_field=UPLOAD_PDF_FIELD,
                q_texts=[PDF_UPLOAD_Q],
                expect_pdf_upload=True,
            )

        score_result = compute_scores_from_fields(state.fields)
        state.current_field = INTAKE_FIELD
        state.last_question_ids = []
        save_session(state, data_dir=data_dir)
        return _build_bot_payload(
            state,
            score_result,
            next_field=INTAKE_FIELD,
            q_texts=["Slayt sunumunuz var mı? Lütfen sadece **Evet** ya da **Hayır** yazın."],
            expect_pdf_upload=False,
        )

    # ✅ Upload step
    if current_field == UPLOAD_PDF_FIELD:
        if _is_no(user_text):
            state.pdf_gate_done = True
            _reset_wizard_cursor(state)  # 👈 kritik
            save_session(state, data_dir=data_dir)
            return start_or_resume(session_id, data_dir=data_dir)

        score_result = compute_scores_from_fields(state.fields)
        state.current_field = UPLOAD_PDF_FIELD
        state.last_question_ids = []
        save_session(state, data_dir=data_dir)
        return _build_bot_payload(
            state,
            score_result,
            next_field=UPLOAD_PDF_FIELD,
            q_texts=["PDF yükleyin ya da **Hayır** yazıp devam edin."],
            expect_pdf_upload=True,
        )

    # 1) store raw answer (optional)
    if question_id:
        set_answer(state, question_id, user_text)

    # ✅ 2) RAG: normalize_answer çağırmadan hemen önce
    rag_snips = []
    rag_index_id = getattr(state, "rag_index_id", None)
    if rag_index_id is not None:    
        q = f"{current_field}: {user_text}"
        try:
            rag_snips = retrieve_snippets_for_flow(index_id=rag_index_id, query=q, top_k=4)
        except Exception as e:
            # RAG asla wizard'ı kırmamalı
            print("RAG error:", e)
            rag_snips = []

    # 3) normalize answer
    norm = normalize_answer(current_field, user_text, state.fields, rag_snippets=rag_snips)

    print("CURRENT_FIELD:", current_field)
    print("USER_TEXT:", repr(user_text))
    print("NORM_RAW:", norm)              # dict'i komple gör
    print("NORM_VALUE:", repr(norm.get("value")))
    print("NORM_CONF:", norm.get("confidence"))

    needs = bool(norm.get("needs_clarification", False))
    followup = norm.get("followup_question")

    # 3b) clarification
    if needs and followup:
        state.current_field = current_field
        state.last_question_ids = [question_id] if question_id else []
        save_session(state, data_dir=data_dir)

        score_result = compute_scores_from_fields(state.fields)
        return _build_bot_payload(
            state,
            score_result,
            next_field=current_field,
            q_texts=[str(followup)],
        )

    value = str(norm.get("value", "")).strip()
    confidence = float(norm.get("confidence", 0.7))

    # 4) update canonical field
    update_field(
        state,
        field_name=current_field,
        value=value,
        source="guided",
        confidence=confidence,
        evidence=f"User answer to {question_id}" if question_id else "User answer",
    )

    print("FIELDS_KEYS:", list(state.fields.keys()))
    print("STATE_FIELD:", state.fields.get(current_field))

    # 5) scoring
    score_result = compute_scores_from_fields(state.fields)
    weak = get_weak_fields(score_result)

    # 6) next field
    next_field = pick_next_field(score_result, state.fields, weak_fields=weak)

    print("NEXT_FIELD:", next_field)

    # 7) next questions
    qids = question_ids_for_field(score_result, next_field) if next_field else []
    q_texts = resolve_questions(qids)[:2] if qids else []

    # 8) persist
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

    return _build_bot_payload(state, score_result, next_field, q_texts)


# -----------------------------
# PDF handler: called by service.upload_pdf()
# -----------------------------
def handle_pdf_text(
    session_id: str,
    pdf_text: str,
    file_name: str = "slides.pdf",
    stored_path: Optional[str] = None,
    data_dir: str = "data/sessions",
) -> Dict[str, Any]:
    """
    UI uploads pdf -> service extracts text -> calls here with pdf_text.
    We summarize -> fill Background -> mark pdf_gate_done -> continue wizard.
    """
    state = load_session(session_id, data_dir=data_dir)

    if stored_path:
        attach_uploaded_file(
            state,
            name=file_name,
            path=stored_path,
            file_type="pdf",
            size=len(pdf_text.encode("utf-8")) if pdf_text else None,
        )
        state.pdf_uploaded_path = stored_path

    try:
        summary = summarize_pdf_to_background(pdf_text, state.fields)
    except Exception:
        summary = ""

    if summary:
        new_bg = _append_background(state.fields.get("Background", ""), summary)
        update_field(
            state,
            field_name="Background",
            value=new_bg,
            source="pdf",
            confidence=0.75,
            evidence=f"Auto summary from {file_name}",
        )
        state.pdf_summary = summary
        state.pdf_applied_to_background = True

    # Gate kapanır + wizard cursor temizlenir
    state.pdf_gate_done = True
    _reset_wizard_cursor(state)
    save_session(state, data_dir=data_dir)

    return start_or_resume(session_id, data_dir=data_dir)


def on_pdf_text_extracted(
    session_id: str,
    pdf_text: str,
    file_name: str = "slides.pdf",
    stored_path: str | None = None,
    data_dir: str = "data/sessions",
):
    return handle_pdf_text(
        session_id=session_id,
        pdf_text=pdf_text,
        file_name=file_name,
        stored_path=stored_path,
        data_dir=data_dir,
    )
