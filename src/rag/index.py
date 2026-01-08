from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Dict, Any


@dataclass
class RAGIndex:
    """
    Abstract handle to a vector index.
    Implementation can be Chroma/FAISS/pgvector/etc.
    """
    index_id: str
    meta: Dict[str, Any]


class VectorStore:
    """
    Interface / wrapper for vector store.
    Replace methods with real implementation.
    """
    def __init__(self, base_dir: str = "data/indexes"):
        self.base_dir = base_dir

    def create_index(self, index_id: str) -> RAGIndex:
        # TODO: create persistent storage
        return RAGIndex(index_id=index_id, meta={"store": "stub"})

    def add_texts(
        self,
        index: RAGIndex,
        texts: List[str],
        metadatas: Optional[List[dict]] = None,
    ) -> None:
        # TODO: embed + upsert into vector db
        raise NotImplementedError("VectorStore.add_texts not implemented")

    def query(
        self,
        index: RAGIndex,
        query_text: str,
        top_k: int = 3,
    ) -> List[dict]:
        """
        Return list of hits, each hit should include:
          {"text": "...", "score": 0.0, "metadata": {...}}
        """
        raise NotImplementedError("VectorStore.query not implemented")
