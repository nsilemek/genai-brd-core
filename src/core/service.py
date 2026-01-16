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

# (Eski RAG importları durabilir; add_wiki_documents artık bunları kullanmıyor)
# from ..rag.confluence import fetch_confluence_pages
# from ..rag.ingest import build_or_update_index

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
 
    _auto_ingest_confluence_if_configured(state.session_id, data_dir=data_dir)
 
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

def _auto_ingest_confluence_if_configured(session_id: str, data_dir: str = "data/sessions"):
    base_url = os.getenv("CONFLUENCE_BASE_URL", "").strip()
    username = os.getenv("CONFLUENCE_USERNAME", "").strip()
    token = os.getenv("CONFLUENCE_API_TOKEN", "").strip()
    space = os.getenv("CONFLUENCE_SPACE_KEY", "").strip()
    limit = int(os.getenv("CONFLUENCE_LIMIT", "50") or 50)
    page_ids_str = os.getenv("CONFLUENCE_PAGE_IDS", "").strip()
    #split string with comma to list from config
    page_ids = [pid.strip() for pid in page_ids_str.split(",")] if page_ids_str else None

    if not (base_url and username and token and space):
        print("[Service] Confluence env missing -> auto-ingest skipped", flush=True)
        return
 
    print("[Service] Auto-ingest starting...", flush=True)
    rep = add_wiki_documents(
        session_id=session_id,
        wiki_type="confluence",
        base_url=base_url,
        username=username,
        api_token=token,
        space_key=space,
        limit=limit,
        page_ids=page_ids
    )
    print("[Service] Auto-ingest report:", rep, flush=True)

# -----------------------------
# Wiki -> RAG (Confluence)
# -----------------------------
def add_wiki_documents(
    session_id: str,
    wiki_type: str,
    base_url: str,
    username: str,
    api_token: str,
    space_key: str | None = None,
    limit: int = 50,
    page_ids: list[str] | None = None,
    data_dir: str = "data/sessions",
    index_dir: str = "data/indexes",
) -> Dict[str, Any]:
    print(f"[Service] add_wiki_documents CALLED for session {session_id} and wiki_type {wiki_type}")
    """
    Pull wiki documents (Confluence) and build a session-scoped RAG index.

    HARD RULES:
    - must be optional
    - must never crash wizard (demo-safe)
    - must work only by setting state.rag_index_id

    Returns:
      {
        "session_id": ...,
        "index_id": ...,
        "documents_count": int,
        "chunks_count": int,
        "errors": list[str]
      }
    """
    state = load_session(session_id, data_dir=data_dir)
    print(f"[Service] Adding wiki documents for session {session_id} using Confluence at {base_url}")
    # Demo-safe: everything inside try/except
    try:
        # Use new pipeline
        from ..rag.index import get_default_vector_store
        from ..rag.wiki_ingest import ingest_wiki_from_config_report

        # Ensure vector store uses configured dirs
        os.environ.setdefault("VRAI_RAG_BASE_DIR", index_dir)

        vector_store = get_default_vector_store()
        print(f"[Service] Vector store initialized: {vector_store}")
        report = ingest_wiki_from_config_report(
            wiki_type=wiki_type,
            vector_store=vector_store,
            page_ids=page_ids,
            space_key=space_key,
            limit=limit,
            index_id=getattr(state, "rag_index_id", None),  # varsa update edebilir
            base_url=base_url,
            username=username,
            api_token=api_token,
        )
        print(f"[Service] Ingest wiki report: {report}")

        index_id = report.get("index_id")

        # Save pointer to session ONLY if we have an index_id
        if index_id:
            # state model strict olsa bile demo-safe şekilde yaz
            try:
                setattr(state, "rag_index_id", index_id)
            except Exception:
                # strict dataclass ise buraya düşebilir; yine de wizard kırmayalım
                pass

            save_session(state, data_dir=data_dir)

        return {
            "session_id": session_id,
            "index_id": index_id,
            "documents_count": int(report.get("documents_count", 0) or 0),
            "chunks_count": int(report.get("chunks_count", 0) or 0),
            "errors": report.get("errors", []) or [],
        }

    except Exception as e:
        # Absolute demo-safe fallback
        return {
            "session_id": session_id,
            "index_id": getattr(state, "rag_index_id", None),
            "documents_count": 0,
            "chunks_count": 0,
            "errors": [f"add_wiki_documents failed (demo-safe): {e}"],
        }


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
    os.makedirs(upload_dir, exist_ok=True)

    safe_name = re.sub(r"[^a-zA-Z0-9._-]+", "_", filename).strip("_") or "slides.pdf"
    path = Path(upload_dir) / f"{session_id}_{safe_name}"
    path.write_bytes(file_bytes)

    try:
        state = load_session(session_id, data_dir=data_dir)
        setattr(state, "pdf_uploaded_path", str(path))
        save_session(state, data_dir=data_dir)
    except Exception:
        pass

    extracted_text = _extract_text_from_pdf_stub(str(path))

    return on_pdf_text_extracted(
        session_id=session_id,
        pdf_text=extracted_text,
        file_name=safe_name,
        stored_path=str(path),
        data_dir=data_dir,
    )


def _extract_text_from_pdf_stub(pdf_path: str, max_chars: int = 6000) -> str:
    try:
        from pypdf import PdfReader  # type: ignore

        reader = PdfReader(pdf_path)
        chunks = []
        for page in reader.pages[:12]:
            txt = page.extract_text() or ""
            if txt.strip():
                chunks.append(txt.strip())
        text = "\n\n".join(chunks).strip()
        if text:
            return text[:max_chars]
    except Exception:
        pass

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
