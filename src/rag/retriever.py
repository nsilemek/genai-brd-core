from __future__ import annotations

from typing import List, Optional

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
    Field-based retrieval (legacy / optional).
    Token-safe snippets.
    """
    if not index_id:
        return []

    query = FIELD_TO_QUERY.get(field_name, field_name)
    index = RAGIndex(index_id=index_id, meta={})

    try:
        hits = vector_store.query(index, query_text=query, top_k=top_k)
    except NotImplementedError:
        return []
    except Exception:
        return []

    snippets: List[str] = []
    for h in hits[:top_k]:
        t = (h.get("text") or "").strip()
        if not t:
            continue
        snippets.append(t[:max_chars_each])

    return snippets


# -------------------------------------------------------------------
# ✅ BACKWARD/INTEGRATION-FRIENDLY WRAPPER (for flow.py)
# -------------------------------------------------------------------
def retrieve_snippets_for_flow(
    *,
    index_id: str,
    query: str,
    top_k: int = 4,
    max_chars_each: int = 700,
    vector_store: Optional[VectorStore] = None,
) -> List[str]:
    """
    Flow.py'nin beklediği arayüz:
      retrieve_snippets_for_flow(index_id=..., query="Field: user text", top_k=4)

    CRITICAL:
    - query string (Field + user_text) gerçekten retrieval sorgusunda kullanılmalı.
    - Demo-safe: hiçbir durumda wizard crash etmemeli -> [] döner.
    """
    if not index_id:
        return []

    q = (query or "").strip()
    if not q:
        return []

    # field_name ayıkla (opsiyonel, query zenginleştirme için)
    field_name = "generic"
    if ":" in q:
        left = q.split(":", 1)[0].strip()
        if left:
            field_name = left

    # vector_store sağlanmadıysa default üret
    if vector_store is None:
        try:
            from .index import get_default_vector_store  # type: ignore

            vector_store = get_default_vector_store()
        except Exception:
            return []

    # Query text'i zenginleştir: field mapping + user_text
    mapped = FIELD_TO_QUERY.get(field_name, field_name)
    query_text = f"{mapped} | {q}" if mapped and mapped not in q else q

    try:
        index = RAGIndex(index_id=index_id, meta={})
        hits = vector_store.query(index, query_text=query_text, top_k=top_k)
    except NotImplementedError:
        return []
    except Exception:
        return []

    snippets: List[str] = []
    for h in hits[:top_k]:
        t = (h.get("text") or "").strip()
        if not t:
            continue
        snippets.append(t[:max_chars_each])

    return snippets
