from __future__ import annotations

import os
from typing import Any, Dict, Optional

from .state import create_session as _create_session, load_session
from .flow import start_or_resume, handle_user_message
from .brd_generator import BRDGenerator
from ..export.exporter_docx import export_docx_file
from ..export.exporter_txt import export_txt_file


def create_session(data_dir: str = "data/sessions") -> Dict[str, Any]:
    state = _create_session(data_dir=data_dir)
    payload = start_or_resume(state.session_id, data_dir=data_dir)
    return payload


def resume(session_id: str, data_dir: str = "data/sessions") -> Dict[str, Any]:
    return start_or_resume(session_id, data_dir=data_dir)


def message(
    session_id: str,
    current_field: str,
    user_text: str,
    question_id: Optional[str] = None,
    data_dir: str = "data/sessions",
) -> Dict[str, Any]:
    return handle_user_message(
        session_id=session_id,
        user_text=user_text,
        current_field=current_field,
        question_id=question_id,
        data_dir=data_dir,
    )


def preview(session_id: str, data_dir: str = "data/sessions") -> Dict[str, Any]:
    state = load_session(session_id, data_dir=data_dir)
    gen = BRDGenerator()
    sections = gen.generate_preview(state.fields, rag_snippets_by_section=None)
    return {"session_id": session_id, "sections": sections}


def export(
    session_id: str,
    fmt: str = "docx",
    data_dir: str = "data/sessions",
    out_dir: str = "data/exports",
) -> Dict[str, Any]:
    state = load_session(session_id, data_dir=data_dir)
    os.makedirs(out_dir, exist_ok=True)

    if fmt.lower() == "txt":
        path = export_txt_file(out_dir, session_id, state.fields, scores=state.scores)
        return {"session_id": session_id, "format": "txt", "path": path}

    path = export_docx_file(out_dir, session_id, state.fields, scores=state.scores)
    return {"session_id": session_id, "format": "docx", "path": path}
