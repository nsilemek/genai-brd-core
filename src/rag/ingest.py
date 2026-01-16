from __future__ import annotations

import os
import re
import uuid
from typing import Any, Dict, List, Optional

from .index import VectorStore, RAGIndex


# ------------------------------------------------------------
# Optional: file text extraction (NOT used by wiki pipeline)
# ------------------------------------------------------------
def extract_text(file_path: str) -> str:
    """
    Demo-safe file extraction (optional).
    - Supports .txt / .md
    - For pdf/docx keep stub (do not crash caller unexpectedly: raise NotImplementedError)
    """
    ext = os.path.splitext(file_path)[1].lower()
    if ext in {".txt", ".md"}:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

    raise NotImplementedError(f"Text extraction not implemented for: {ext}")


# ------------------------------------------------------------
# Core: chunking (USED by wiki_ingest.py)
# ------------------------------------------------------------
def chunk_text(
    text: str,
    max_chars: int = 3500,
    overlap: int = 200,
    min_chunk_chars: int = 200,
) -> List[str]:
    """
    Confluence/wiki text için chunking.

    Goals:
    - Paragraph/headings boundaries are preferred
    - Overlap for retrieval continuity
    - Falls back to char-splitting for very long paragraphs
    - Demo-safe: never raises

    Args:
      max_chars: target upper bound per chunk
      overlap: characters to overlap between consecutive chunks
      min_chunk_chars: avoid extremely tiny chunks (merged when possible)
    """
    try:
        t = (text or "").strip()
        if not t:
            return []

        # Normalize whitespace (keep paragraph breaks)
        t = re.sub(r"\r\n?", "\n", t)
        t = re.sub(r"[ \t]+\n", "\n", t)
        t = re.sub(r"\n{3,}", "\n\n", t).strip()

        # Split into paragraphs (blank-line separated)
        paras = [p.strip() for p in t.split("\n\n") if p.strip()]
        if not paras:
            paras = [t]

        chunks: List[str] = []
        buf: List[str] = []
        buf_len = 0

        def flush_buf() -> None:
            nonlocal buf, buf_len, chunks
            if not buf:
                return
            combined = "\n\n".join(buf).strip()
            if combined:
                chunks.append(combined)
            buf = []
            buf_len = 0

        for p in paras:
            # If single paragraph too large -> split it with overlap
            if len(p) > max_chars:
                flush_buf()
                chunks.extend(_split_with_overlap(p, max_chars=max_chars, overlap=overlap))
                continue

            # If adding this paragraph exceeds max -> flush current buffer
            projected = buf_len + (2 if buf else 0) + len(p)
            if projected > max_chars and buf:
                flush_buf()

            buf.append(p)
            buf_len = buf_len + (2 if buf_len else 0) + len(p)

        flush_buf()

        # Post-process: ensure overlap between chunks (paragraph-based overlap)
        if overlap > 0 and len(chunks) > 1:
            chunks = _apply_overlap(chunks, overlap=overlap, max_chars=max_chars)

        # Drop/merge tiny chunks
        chunks = _merge_tiny(chunks, min_chunk_chars=min_chunk_chars, max_chars=max_chars)

        # Final cleanup
        cleaned = []
        for c in chunks:
            c = (c or "").strip()
            if c:
                cleaned.append(c)
        return cleaned

    except Exception:
        # absolute demo-safe fallback
        return _split_with_overlap((text or "").strip(), max_chars=max_chars, overlap=overlap)


def _split_with_overlap(s: str, *, max_chars: int, overlap: int) -> List[str]:
    s = (s or "").strip()
    if not s:
        return []
    overlap = max(0, int(overlap))
    max_chars = max(200, int(max_chars))

    out: List[str] = []
    i = 0
    n = len(s)

    while i < n:
        end = min(i + max_chars, n)
        chunk = s[i:end].strip()
        if chunk:
            out.append(chunk)
        if end >= n:
            break
        i = max(0, end - overlap)

    return out


def _apply_overlap(chunks: List[str], *, overlap: int, max_chars: int) -> List[str]:
    """
    Adds tail overlap from previous chunk to the next chunk.
    Keeps next chunk within max_chars.
    """
    if overlap <= 0 or len(chunks) < 2:
        return chunks

    out = [chunks[0]]
    for i in range(1, len(chunks)):
        prev = out[-1]
        cur = chunks[i]

        tail = prev[-overlap:] if len(prev) > overlap else prev
        merged = (tail + "\n\n" + cur).strip()

        # If merged too big, keep as much as possible from tail
        if len(merged) > max_chars:
            tail2 = tail[-min(overlap, max_chars // 4):]  # small safe tail
            merged = (tail2 + "\n\n" + cur).strip()

        out.append(merged)

    return out


def _merge_tiny(chunks: List[str], *, min_chunk_chars: int, max_chars: int) -> List[str]:
    """
    Merge very small chunks into neighbors when possible.
    """
    if not chunks:
        return []

    min_chunk_chars = max(0, int(min_chunk_chars))
    if min_chunk_chars == 0:
        return chunks

    out: List[str] = []
    for c in chunks:
        c = (c or "").strip()
        if not c:
            continue

        if not out:
            out.append(c)
            continue

        if len(c) < min_chunk_chars:
            # try merge into previous if fits
            prev = out[-1]
            merged = (prev + "\n\n" + c).strip()
            if len(merged) <= max_chars:
                out[-1] = merged
            else:
                out.append(c)
        else:
            out.append(c)

    return out


# ------------------------------------------------------------
# Optional: ingest a local file into VectorStore (not used now)
# ------------------------------------------------------------
def ingest_file(
    file_path: str,
    vector_store: VectorStore,
    max_chunk_chars: int = 3500,
) -> str:
    """
    Optional helper (not used by your current wiki pipeline).
    Creates a new index and ingests file text (txt/md only).
    Demo-safe: returns index_id even if add_texts isn't available.
    """
    index_id = str(uuid.uuid4())
    try:
        text = extract_text(file_path)
        chunks = chunk_text(text, max_chars=max_chunk_chars)
        index = vector_store.create_index(index_id)

        print(f"Ingesting file '{file_path}' into index '{index_id}' with {len(chunks)} chunks.")

        try:
            vector_store.add_texts(
                index,
                chunks,
                metadatas=[{"source": os.path.basename(file_path)}] * len(chunks),
            )
        except NotImplementedError:
            # embeddings not available -> keep demo-safe
            pass
        except Exception:
            pass

    except Exception:
        # still return an index_id for consistency
        pass

    return index_id
