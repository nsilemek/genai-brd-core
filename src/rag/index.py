from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
import os
import hashlib

# requests only needed for Gemma embedding endpoint
try:
    import requests
except Exception:
    requests = None


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
    ChromaDB-based vector store implementation.

    Demo-safe:
      - chromadb yoksa crash etmez
      - embedding backend yoksa query() [] döner
      - add_texts() embedding yoksa NotImplementedError verir (ingest/service yakalamalı)
    """

    def __init__(
        self,
        base_dir: str = "data/indexes",
        embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    ):
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)

        self.client = None
        self.embedder = None

        # -------------------------
        # Embedding mode selection
        # -------------------------
        # EMBEDDING_MODE:
        #   - "local" (default): sentence-transformers
        #   - "gemma": endpoint üzerinden embedding
        self.embedding_mode = os.getenv("EMBEDDING_MODE", "local").strip().lower()

        # Gemma embedding endpoint config (optional)
        self.gemma_url = os.getenv("GEMMA_EMBEDDING_URL", "").strip()
        self.gemma_api_key = os.getenv("GEMMA_API_KEY", "").strip()
        self.gemma_model = os.getenv("GEMMA_MODEL", "gemma-300").strip()
        self.embedding_timeout = float(os.getenv("EMBEDDING_TIMEOUT_SEC", "30") or "30")

        # -------------------------
        # Chroma import demo-safe
        # -------------------------
        try:
            import chromadb
            from chromadb.config import Settings

            self.client = chromadb.PersistentClient(
                path=base_dir,
                settings=Settings(anonymized_telemetry=False),
            )
        except Exception as e:
            print(f"[RAG] Warning: chromadb not available or failed to init: {e}")
            self.client = None

        # -------------------------
        # Local embedding import demo-safe (only if mode=local)
        # -------------------------
        if self.embedding_mode == "local":
            try:
                from sentence_transformers import SentenceTransformer
                self.embedder = SentenceTransformer(embedding_model)
            except Exception as e:
                print(f"[RAG] Warning: Could not load embedding model '{embedding_model}': {e}")
                print("[RAG] Falling back to stub mode (no embeddings).")
                self.embedder = None

    # -------------------------
    # Index
    # -------------------------
    def create_index(self, index_id: str) -> RAGIndex:
        """
        Create or get a ChromaDB collection
        Collection naming: rag_index_<index_id>
        """
        collection_name = f"rag_index_{index_id}"

        # Demo-safe: chroma yoksa bile index handle döndürelim
        if not self.client:
            return RAGIndex(index_id=index_id, meta={"collection_name": collection_name, "store": "stub"})

        try:
            _ = self.client.get_collection(collection_name)
        except Exception:
            _ = self.client.create_collection(
                name=collection_name,
                metadata={"index_id": index_id},
            )

        return RAGIndex(index_id=index_id, meta={"collection_name": collection_name, "store": "chromadb"})

    def _make_id(self, index_id: str, text: str, i: int) -> str:
        h = hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]
        return f"{index_id}_{i}_{h}"

    # -------------------------
    # Embedding
    # -------------------------
    def _embed(self, texts: List[str]) -> List[List[float]]:
        """
        Returns embeddings for given texts.
        - local: sentence-transformers
        - gemma: endpoint call
        """
        if not texts:
            return []

        mode = self.embedding_mode

        if mode == "gemma":
            if requests is None:
                raise NotImplementedError("requests not available for Gemma embedding. Install requests.")
            if not self.gemma_url:
                raise NotImplementedError("GEMMA_EMBEDDING_URL not set for EMBEDDING_MODE=gemma")
            if not self.gemma_api_key:
                raise NotImplementedError("GEMMA_API_KEY not set for EMBEDDING_MODE=gemma")

            headers = {
                "Authorization": f"Bearer {self.gemma_api_key}",
                "Content-Type": "application/json",
            }

            # Most common schema:
            # { "model": "gemma-300", "input": ["text1", "text2"] }
            payload = {"model": self.gemma_model, "input": texts}

            r = requests.post(
                self.gemma_url,
                json=payload,
                headers=headers,
                timeout=self.embedding_timeout,
            )
            r.raise_for_status()
            data = r.json()

            # Try common response shapes:
            # 1) OpenAI-like: {"data":[{"embedding":[...]}, ...]}
            if isinstance(data, dict) and isinstance(data.get("data"), list):
                embs = []
                for item in data["data"]:
                    if isinstance(item, dict) and isinstance(item.get("embedding"), list):
                        embs.append(item["embedding"])
                if embs:
                    return embs

            # 2) {"embeddings":[[...],[...]]}
            if isinstance(data, dict) and isinstance(data.get("embeddings"), list):
                embs = data["embeddings"]
                if embs and isinstance(embs[0], list):
                    return embs

            # 3) {"output":[[...],[...]]} or {"vectors":[...]}
            for key in ("output", "vectors", "vector"):
                if isinstance(data, dict) and isinstance(data.get(key), list):
                    v = data[key]
                    if v and isinstance(v[0], list):
                        return v

            raise ValueError("Unknown Gemma embedding response schema")

        # default: local
        if self.embedder is None:
            raise NotImplementedError("Local embedding model not available. Install sentence-transformers.")
        return self.embedder.encode(texts, show_progress_bar=False).tolist()

    # -------------------------
    # Upsert
    # -------------------------
    def add_texts(
        self,
        index: RAGIndex,
        texts: List[str],
        metadatas: Optional[List[dict]] = None,
    ) -> None:
        """
        Add texts to vector store with embeddings.
        - embedding backend yoksa NotImplementedError (ingest/service yakalamalı)
        """
        if not texts:
            return

        if not self.client:
            raise NotImplementedError("Chroma client not available. Install chromadb.")

        collection_name = index.meta.get("collection_name") or f"rag_index_{index.index_id}"

        try:
            collection = self.client.get_collection(collection_name)
        except Exception:
            collection = self.client.create_collection(
                name=collection_name,
                metadata={"index_id": index.index_id},
            )

        # Prepare metadatas
        if metadatas is None:
            metadatas = [{} for _ in texts]
        elif len(metadatas) != len(texts):
            # demo-safe: mismatch olursa pad/crop
            if len(metadatas) < len(texts):
                metadatas = metadatas + ([{}] * (len(texts) - len(metadatas)))
            else:
                metadatas = metadatas[: len(texts)]

        embeddings = self._embed(texts)
        ids = [self._make_id(index.index_id, t, i) for i, t in enumerate(texts)]

        collection.add(
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
            ids=ids,
        )

    # -------------------------
    # Query
    # -------------------------
    def query(
        self,
        index: RAGIndex,
        query_text: str,
        top_k: int = 3,
    ) -> List[dict]:
        """
        Query the vector store and return list of hits.
        Demo-safe: embedding/chroma yoksa []
        """
        if not query_text:
            return []

        if not self.client:
            return []

        # Embedding yoksa demo-safe boş dön
        try:
            query_embedding = self._embed([query_text])[0]
        except Exception:
            return []

        collection_name = index.meta.get("collection_name") or f"rag_index_{index.index_id}"

        try:
            collection = self.client.get_collection(collection_name)
        except Exception:
            return []

        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
        )

        hits: List[dict] = []
        docs = (results.get("documents") or [[]])[0]
        metas = (results.get("metadatas") or [[]])[0]
        dists = (results.get("distances") or [[]])[0]

        for i, doc in enumerate(docs):
            if not doc:
                continue
            dist = dists[i] if i < len(dists) else 1.0
            score = 1.0 - float(dist)
            meta = metas[i] if i < len(metas) else {}
            hits.append({"text": doc, "score": score, "metadata": meta or {}})

        return hits


def get_default_vector_store() -> VectorStore:
    """
    Retriever wrapper burayı çağırır.
    Demo-safe: env yoksa default değerlerle gelir.
    """
    base_dir = os.getenv("VRAI_RAG_BASE_DIR", "data/indexes")
    embedding_model = os.getenv(
        "VRAI_RAG_EMBEDDING_MODEL",
        "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    )
    return VectorStore(base_dir=base_dir, embedding_model=embedding_model)
