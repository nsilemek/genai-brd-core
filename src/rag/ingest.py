from __future__ import annotations

import os
import uuid
from typing import List, Tuple

from .index import VectorStore, RAGIndex


def extract_text(file_path: str) -> str:
    """
    Stub: implement PDF/DOCX/TXT extraction later.
    For MVP you can support TXT first.
    """
    ext = os.path.splitext(file_path)[1].lower()
    if ext in [".txt", ".md"]:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

    # TODO: pdf/docx extraction
    raise NotImplementedError(f"Text extraction not implemented for: {ext}")


def chunk_text(text: str, max_chars: int = 3500) -> List[str]:
    """
    Simple char-based chunking (good enough as stub).
    """
    text = (text or "").strip()
    if not text:
        return []
    chunks = []
    i = 0
    while i < len(text):
        chunks.append(text[i:i + max_chars])
        i += max_chars
    return chunks


def ingest_file(
    file_path: str,
    vector_store: VectorStore,
    max_chunk_chars: int = 3500,
) -> str:
    """
    Returns index_id to store in session state.
    """
    text = extract_text(file_path)
    chunks = chunk_text(text, max_chars=max_chunk_chars)

    index_id = str(uuid.uuid4())
    index = vector_store.create_index(index_id)

    # TODO: add embeddings
    # vector_store.add_texts(index, chunks, metadatas=[{"source": os.path.basename(file_path)}]*len(chunks))

    # For now: just return id; store not populated in stub.
    return index.index_id
