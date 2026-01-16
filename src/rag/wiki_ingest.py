from __future__ import annotations

from typing import List, Optional, Dict, Any, Tuple
import uuid

from .wiki_client import WikiClient, create_wiki_client
from .index import VectorStore, RAGIndex
from .ingest import chunk_text


def _normalize_page_url(wiki_client: WikiClient, page: Dict[str, Any]) -> str:
    url = ""
    links = page.get("_links") or {}
    url = links.get("webui") or page.get("url") or ""

    if not url:
        return ""

    if url.startswith("http://") or url.startswith("https://"):
        return url

    base_url = getattr(wiki_client, "base_url", "") or getattr(wiki_client, "baseUrl", "") or ""
    base_url = base_url.rstrip("/")

    if not base_url:
        return url

    if not url.startswith("/"):
        url = "/" + url
    return base_url + url


def ingest_wiki_pages(
    wiki_client: WikiClient,
    vector_store: VectorStore,
    page_ids: Optional[List[str]] = None,
    space_key: Optional[str] = None,
    limit: int = 100,
    max_chunk_chars: int = 3500,
    index_id: Optional[str] = None,
) -> str:
    """
    Backward-compatible: returns only index_id.
    Demo-safe: no exception should escape.
    """
    print("[WikiIngest] Starting wiki ingestion...")
    report = ingest_wiki_pages_report(
        wiki_client=wiki_client,
        vector_store=vector_store,
        page_ids=page_ids,
        space_key=space_key,
        limit=limit,
        max_chunk_chars=max_chunk_chars,
        index_id=index_id,
    )
    print("[WikiIngest] RAG REPORT:", report)
    print("[WikiIngest] CHROMA CLIENT OK:", vector_store.client is not None)
    print("[WikiIngest] BASE_DIR:", vector_store.base_dir)
    return report["index_id"]


def ingest_wiki_pages_report(
    wiki_client: WikiClient,
    vector_store: VectorStore,
    page_ids: Optional[List[str]] = None,
    space_key: Optional[str] = None,
    limit: int = 100,
    max_chunk_chars: int = 3500,
    index_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    ✅ NEW: returns report for UI/service:
      {
        "index_id": str,
        "documents_count": int,
        "chunks_count": int,
        "errors": list[str]
      }

    Demo-safe guarantees:
    - Never raises
    - Always returns index_id
    """

    errors: List[str] = []

    if not index_id:
        index_id = str(uuid.uuid4())

    # Create/ensure index/collection
    try:
        index = vector_store.create_index(index_id)
    except Exception as e:
        errors.append(f"create_index failed: {e}")
        index = RAGIndex(index_id=index_id, meta={"collection_name": f"rag_index_{index_id}"})

    print(f"[WikiIngest] Using index ID: {index_id}")
    # Fetch pages
    pages: List[Dict[str, Any]] = []
    try:
        if page_ids:
            for pid in page_ids:
                try:
                    p = wiki_client.fetch_page(pid)
                    print(f"Fetched page ID {pid}: {p.get('title', 'No Title')}")
                    if p:
                        pages.append(p)
                except Exception as e:
                    errors.append(f"fetch_page {pid} failed: {e}")
        else:
            pages = wiki_client.fetch_pages(space_key=space_key, limit=limit) or []
    except Exception as e:
        errors.append(f"fetch_pages failed: {e}")
        pages = []

    # Extract + chunk
    all_chunks: List[str] = []
    all_metadatas: List[dict] = []

    print(f"[WikiIngest] Pages fetched: {len(pages)}", flush=True)
    print(f"[WikiIngest] Total chunks prepared: {len(all_chunks)}", flush=True)

    for page in pages:
        try:
            text = wiki_client.extract_text(page)
            if not text or len(text.strip()) < 50:
                continue

            chunks = chunk_text(text, max_chars=max_chunk_chars) or []
            if not chunks:
                continue

            page_title = page.get("title") or page.get("displayTitle") or "Unknown"
            page_id_val = page.get("id") or page.get("pageid") or "unknown"
            page_url = _normalize_page_url(wiki_client, page)

            for i, ch in enumerate(chunks):
                c = (ch or "").strip()
                if not c:
                    continue
                all_chunks.append(c)
                all_metadatas.append(
                    {
                        "source": "wiki",
                        "page_id": str(page_id_val),
                        "page_title": str(page_title),
                        "chunk_index": i,
                        "total_chunks": len(chunks),
                        "url": page_url,
                    }
                )
        except Exception as e:
            pid = page.get("id", "unknown")
            errors.append(f"process page {pid} failed: {e}")

    # Add to store
    if all_chunks:
        try:
            vector_store.add_texts(index, all_chunks, metadatas=all_metadatas)
        except NotImplementedError as e:
            # embeddings yoksa demo-safe: sadece retrieval devre dışı kalır
            errors.append(f"vector_store not ready: {e}")
        except Exception as e:
            errors.append(f"add_texts failed: {e}")

    return {
        "index_id": index_id,
        "documents_count": len(pages),
        "chunks_count": len(all_chunks),
        "errors": errors,
    }


def ingest_wiki_from_config(
    wiki_type: str,
    vector_store: VectorStore,
    page_ids: Optional[List[str]] = None,
    space_key: Optional[str] = None,
    limit: int = 100,
    index_id: Optional[str] = None,
    **wiki_kwargs,
) -> str:
    """
    Backward-compatible: returns only index_id
    """
    report = ingest_wiki_from_config_report(
        wiki_type=wiki_type,
        vector_store=vector_store,
        page_ids=page_ids,
        space_key=space_key,
        limit=limit,
        index_id=index_id,
        **wiki_kwargs,
    )
    return report["index_id"]


def ingest_wiki_from_config_report(
    wiki_type: str,
    vector_store: VectorStore,
    page_ids: Optional[List[str]] = None,
    space_key: Optional[str] = None,
    limit: int = 100,
    index_id: Optional[str] = None,
    **wiki_kwargs,
) -> Dict[str, Any]:
    """
    ✅ NEW: config -> wiki_client -> ingest + report
    Demo-safe: never raises, always returns index_id
    """
    errors: List[str] = []
    print(f"[WikiIngest] ingest_wiki_from_config_report called with index_id: {index_id}")
    if not index_id:
        index_id = str(uuid.uuid4())

    try:
        if wiki_type.lower() != "confluence":
            raise ValueError(f"Only Confluence is supported. Got: {wiki_type}")

        wiki_client = create_wiki_client(**wiki_kwargs)
        print(f"[WikiIngest] Wiki client created")
        rep = ingest_wiki_pages_report(
            wiki_client=wiki_client,
            vector_store=vector_store,
            page_ids=page_ids,
            space_key=space_key,
            limit=limit,
            index_id=index_id
        )
        print(f"[WikiIngest] Ingest wiki report: {rep}")
        return rep
    except Exception as e:
        errors.append(f"ingest_wiki_from_config failed: {e}")
        return {
            "index_id": index_id,
            "documents_count": 0,
            "chunks_count": 0,
            "errors": errors,
        }
