from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .constants import BRD_FIELDS
from .types import FieldUpdate, SessionState


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def create_default_fields() -> Dict[str, Any]:
    return {k: "" for k in BRD_FIELDS}


def session_path(session_id: str, data_dir: str = "data/sessions") -> str:
    return os.path.join(data_dir, f"{session_id}.json")


# -----------------------------
# Public API expected by service.py / flow.py
# -----------------------------
def create_session(data_dir: str = "data/sessions") -> SessionState:
    """
    Creates a new session with defaults.
    service.py expects: create_session()
    """
    _ensure_dir(data_dir)
    session_id = str(uuid.uuid4())

    state = SessionState(
        session_id=session_id,
        created_at=_now_iso(),
        fields=create_default_fields(),

        # ensure these exist for backward/forward compatibility
        answers={},
        field_updates=[],
        system_summary="",
        rag_index_id=None,
        uploaded_files=[],
        scores=None,
        current_field=None,
        last_question_ids=[],

        # PDF gate (persisted)
        pdf_gate_done=False,
        pdf_uploaded_path=None,
        pdf_summary="",
        pdf_applied_to_background=False,

        # optional extension
        privacy_ruleset_output=None,
    )

    save_session(state, data_dir=data_dir)
    return state


def save_session(state: SessionState, data_dir: str = "data/sessions") -> str:
    _ensure_dir(data_dir)
    path = session_path(state.session_id, data_dir=data_dir)
    data = asdict(state)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path


def load_session(session_id: str, data_dir: str = "data/sessions") -> SessionState:
    """
    Loads a session JSON and rehydrates dataclasses.
    Backward-compatible: safely defaults any new fields for older sessions.
    """
    path = session_path(session_id, data_dir=data_dir)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Session not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Backward-compat: accept older naming if exists
    legacy_intake_done = bool(data.get("intake_done", False))
    legacy_upload_pdf_path = data.get("upload_pdf_path")
    legacy_intake_summary = data.get("intake_summary", "")

    state = SessionState(
        session_id=data["session_id"],
        created_at=data["created_at"],
        fields=data.get("fields", {}),

        answers=data.get("answers", {}),
        field_updates=[FieldUpdate(**fu) for fu in data.get("field_updates", [])],
        system_summary=data.get("system_summary", ""),
        rag_index_id=data.get("rag_index_id"),
        uploaded_files=data.get("uploaded_files", []),
        scores=data.get("scores"),
        current_field=data.get("current_field"),
        last_question_ids=data.get("last_question_ids", []),

        # PDF gate (new canonical names)
        pdf_gate_done=bool(data.get("pdf_gate_done", legacy_intake_done)),
        pdf_uploaded_path=data.get("pdf_uploaded_path", legacy_upload_pdf_path),
        pdf_summary=str(data.get("pdf_summary", legacy_intake_summary) or ""),
        pdf_applied_to_background=bool(data.get("pdf_applied_to_background", False)),

        # optional future extension
        privacy_ruleset_output=data.get("privacy_ruleset_output"),
    )

    # Ensure any missing BRD fields exist (backward compatible)
    for k in BRD_FIELDS:
        state.fields.setdefault(k, "")

    return state


def update_field(
    state: SessionState,
    field_name: str,
    value: Any,
    source: str,
    confidence: float = 1.0,
    evidence: Optional[str] = None,
) -> None:
    state.fields[field_name] = value
    state.field_updates.append(
        FieldUpdate(
            ts=_now_iso(),
            field=field_name,
            value=value,
            source=source,
            confidence=float(confidence),
            evidence=evidence,
        )
    )


def set_answer(state: SessionState, question_id: str, raw_text: str) -> None:
    state.answers[question_id] = raw_text


def attach_uploaded_file(
    state: SessionState,
    name: str,
    path: str,
    file_type: str,
    size: Optional[int] = None,
) -> None:
    """
    Stores upload metadata into session (useful for PDF slides, etc.)
    """
    state.uploaded_files.append(
        {"name": name, "path": path, "type": file_type, "size": size, "ts": _now_iso()}
    )
