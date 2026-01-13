from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, Optional

from .bootstrap import ensure_data_dirs
from .state import (
    create_session as _create_session,
    load_session,
    save_session,
)
from .flow import start_or_resume, handle_user_message, on_pdf_text_extracted
from .brd_generator import BRDGenerator
from ..export.exporter_docx import export_docx_file
from ..export.exporter_txt import export_txt_file

ensure_data_dirs()

# NOTE:
# This module is the main integration point for external tools/UI.
# Behavior is controlled via environment variables:
# - USE_LLM=0 -> stub mode (demo-safe)
# - USE_LLM=1 -> LLM-enabled normalization


# -----------------------------
# Sessions
# -----------------------------
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


# -----------------------------
# PDF Upload
# -----------------------------
def upload_pdf(
    session_id: str,
    file_bytes: bytes,
    filename: str = "slides.pdf",
    data_dir: str = "data/sessions",
    upload_dir: str = "data/uploads",
) -> Dict[str, Any]:
    """
    UI uploads PDF here (slides).

    Behavior:
      - Save file to data/uploads/<session_id>_<filename>
      - Extract text (lightweight; uses pypdf if available, else stub message)
      - Call flow.on_pdf_text_extracted(session_id, extracted_text, file_name, stored_path)
        so flow can:
          - summarize -> Background
          - mark intake_done
          - continue normal BRD flow
    """
    os.makedirs(upload_dir, exist_ok=True)

    safe_name = re.sub(r"[^a-zA-Z0-9._-]+", "_", filename).strip("_") or "slides.pdf"
    path = Path(upload_dir) / f"{session_id}_{safe_name}"
    path.write_bytes(file_bytes)

    # (Opsiyonel) state'e yalnızca convenience pointer yazalım (çift attach yapmayalım!)
    # attach_uploaded_file(...) zaten flow.handle_pdf_text içinde yapılıyor.
    try:
        state = load_session(session_id, data_dir=data_dir)
        setattr(state, "pdf_uploaded_path", str(path))
        save_session(state, data_dir=data_dir)
    except Exception:
        pass

    extracted_text = _extract_text_from_pdf_stub(str(path))

    # 🔑 flow tarafına dosya adı + path gönderiyoruz (Background'a ekler, intake_done yapar)
    return on_pdf_text_extracted(
        session_id=session_id,
        pdf_text=extracted_text,
        file_name=safe_name,
        stored_path=str(path),
        data_dir=data_dir,
    )


def _extract_text_from_pdf_stub(pdf_path: str, max_chars: int = 6000) -> str:
    """
    Very light demo-safe PDF extraction.

    - If pypdf is installed, extracts text from first N pages.
    - Otherwise returns a stub text so demo doesn't break.
    """
    # ---- Optional lightweight extraction (ONLY if pypdf installed) ----
    try:
        from pypdf import PdfReader  # type: ignore

        reader = PdfReader(pdf_path)
        chunks = []
        for page in reader.pages[:12]:  # limit pages for safety
            txt = page.extract_text() or ""
            if txt.strip():
                chunks.append(txt.strip())
        text = "\n\n".join(chunks).strip()
        if text:
            return text[:max_chars]
    except Exception:
        pass

    # fallback: still demo works, just less smart
    name = os.path.basename(pdf_path)
    return (
        f"PDF uploaded: {name}\n"
        "Slide text extraction is currently in stub mode.\n"
        "If you add 'pypdf', text extraction will run automatically.\n"
    )


# -----------------------------
# Preview + Export
# -----------------------------
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
