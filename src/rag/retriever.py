from __future__ import annotations

from typing import List

from .index import VectorStore, RAGIndex
from .field_queries import FIELD_TO_QUERY


def retrieve_snippets(
    field_name: str,
    index_id: str,
    vector_store: VectorStore,
    top_k: int = 3,
    max_chars_each: int = 700,
) -> List[str]:
    """
    Returns list[str] snippets to feed into LLM context.
    This is token-safe by design (short clipped text).
    """
    if not index_id:
        return []

    query = FIELD_TO_QUERY.get(field_name, field_name)
    index = RAGIndex(index_id=index_id, meta={})

    try:
        hits = vector_store.query(index, query_text=query, top_k=top_k)
    except NotImplementedError:
        return []  # stub: no store yet

    snippets = []
    for h in hits[:top_k]:
        t = (h.get("text") or "").strip()
        if not t:
            continue
        snippets.append(t[:max_chars_each])

    return snippets
