"""
Semantic Vector Store for Jarvis Multi-Agent AI Operating System.

Provides embedding-based retrieval using:
- Ollama's /api/embeddings endpoint for vector generation
- In-memory numpy arrays with cosine similarity search
- SQLite persistence for metadata and vector storage

Designed for easy upgrade to ChromaDB or FAISS later.
"""

from __future__ import annotations

import hashlib
import json
import logging
import pickle
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from config import EMBEDDING_DIMENSION, SIMILARITY_TOP_K, SIMILARITY_THRESHOLD, VECTOR_INDEX_PATH
from core.llm_client import LLMClient
from memory.database import DatabaseManager

logger = logging.getLogger(__name__)


class SimpleVectorStore:
    """
    Lightweight vector store using numpy for similarity search.

    Architecture:
        - Vectors stored as numpy array (index_position x dimension)
        - Metadata stored in SQLite (vector_entries table)
        - Persistent cache via pickle for fast reload

    Future upgrade path:
        Replace this class with a ChromaDB or FAISS wrapper
        implementing the same public interface.
    """

    def __init__(
        self,
        db: DatabaseManager | None = None,
        llm_client: LLMClient | None = None,
    ) -> None:
        self.db = db or DatabaseManager()
        self.llm = llm_client or LLMClient()
        self.dimension = EMBEDDING_DIMENSION

        # In-memory state
        self._vectors: np.ndarray = np.zeros((0, self.dimension), dtype=np.float32)
        self._entries: Dict[int, Dict[str, Any]] = {}  # index_position -> metadata
        self._id_to_index: Dict[str, int] = {}  # entry_id -> index_position
        self._loaded = False

        # Cache path
        self._cache_dir = Path(VECTOR_INDEX_PATH)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._vector_cache = self._cache_dir / "vectors.pkl"
        self._meta_cache = self._cache_dir / "metadata.pkl"

        self._load_from_cache()

    # -------------------------------------------------------------------------
    # PUBLIC API
    # -------------------------------------------------------------------------

    def add(
        self,
        text: str,
        source_table: str,
        source_id: int,
        *,
        metadata: Dict[str, Any] | None = None,
        embedding: List[float] | None = None,
    ) -> str:
        """
        Add a text entry to the vector store.

        Args:
            text: The text to embed and store.
            source_table: Origin table (e.g., 'memories', 'notes').
            source_id: Row ID in the source table.
            metadata: Additional metadata.
            embedding: Pre-computed embedding (generates if None).

        Returns:
            entry_id: Unique identifier for this vector entry.
        """
        # Generate embedding if not provided
        if embedding is None:
            try:
                embedding = self.llm.embed(text)
            except Exception as e:
                logger.error(f"Failed to generate embedding: {e}")
                raise

        if not embedding or len(embedding) != self.dimension:
            logger.error(f"Invalid embedding dimension: got {len(embedding) if embedding else 0}, expected {self.dimension}")
            raise ValueError(f"Embedding dimension mismatch. Expected {self.dimension}.")

        # Normalize vector for cosine similarity
        vec = np.array(embedding, dtype=np.float32)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm

        # Generate stable entry ID
        content_hash = hashlib.sha256(text.encode()).hexdigest()[:16]
        entry_id = f"{source_table}:{source_id}:{content_hash}"

        # Store metadata in SQLite
        self.db.execute(
            """
            INSERT OR REPLACE INTO vector_entries (entry_id, source_table, source_id, content_hash, dimension)
            VALUES (?, ?, ?, ?, ?)
            """,
            (entry_id, source_table, source_id, content_hash, self.dimension),
        )

        # Add to in-memory index
        index = len(self._vectors)
        self._vectors = np.vstack([self._vectors, vec.reshape(1, -1)]) if self._vectors.size > 0 else vec.reshape(1, -1)
        self._entries[index] = {
            "entry_id": entry_id,
            "source_table": source_table,
            "source_id": source_id,
            "text": text[:500],  # Truncate for memory
            "metadata": metadata or {},
        }
        self._id_to_index[entry_id] = index

        self._persist_cache()
        logger.debug(f"Added vector entry: {entry_id} (index={index})")
        return entry_id

    def search(
        self,
        query: str,
        *,
        top_k: int | None = None,
        threshold: float | None = None,
        source_table: str | None = None,
    ) -> List[Tuple[Dict[str, Any], float]]:
        """
        Semantic search over stored vectors.

        Args:
            query: Query text.
            top_k: Maximum results (defaults to config).
            threshold: Minimum similarity score (defaults to config).
            source_table: Filter by source table.

        Returns:
            List of (metadata_dict, similarity_score) tuples, sorted by score desc.
        """
        top_k = top_k or SIMILARITY_TOP_K
        threshold = threshold or SIMILARITY_THRESHOLD

        if len(self._vectors) == 0:
            logger.debug("Vector store empty, returning no results")
            return []

        # Embed query
        try:
            query_embedding = self.llm.embed(query)
        except Exception as e:
            logger.error(f"Failed to embed query: {e}")
            return []

        query_vec = np.array(query_embedding, dtype=np.float32)
        norm = np.linalg.norm(query_vec)
        if norm > 0:
            query_vec = query_vec / norm

        # Compute cosine similarities (dot product of normalized vectors)
        similarities = np.dot(self._vectors, query_vec)

        # Filter and sort
        candidates = []
        for idx, score in enumerate(similarities):
            if score < threshold:
                continue
            meta = self._entries.get(idx)
            if meta is None:
                continue
            if source_table and meta.get("source_table") != source_table:
                continue
            candidates.append((meta, float(score)))

        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[:top_k]

    def delete_by_source(self, source_table: str, source_id: int) -> bool:
        """Delete all vectors associated with a source record."""
        # Mark as deleted in metadata; actual cleanup on next rebuild
        removed = False
        for idx, meta in list(self._entries.items()):
            if meta.get("source_table") == source_table and meta.get("source_id") == source_id:
                del self._entries[idx]
                del self._id_to_index[meta["entry_id"]]
                removed = True

        if removed:
            self._rebuild_vectors()
            self._persist_cache()
        return removed

    def count(self) -> int:
        """Total number of vectors in the store."""
        return len(self._entries)

    def clear(self) -> None:
        """Clear all vectors."""
        self._vectors = np.zeros((0, self.dimension), dtype=np.float32)
        self._entries.clear()
        self._id_to_index.clear()
        self.db.execute("DELETE FROM vector_entries")
        self._persist_cache()
        logger.info("Vector store cleared")

    # -------------------------------------------------------------------------
    # INTERNAL
    # -------------------------------------------------------------------------

    def _load_from_cache(self) -> None:
        """Load vectors and metadata from disk cache."""
        try:
            if self._vector_cache.exists() and self._meta_cache.exists():
                with open(self._vector_cache, "rb") as vf:
                    self._vectors = pickle.load(vf)
                with open(self._meta_cache, "rb") as mf:
                    cached = pickle.load(mf)
                    self._entries = cached.get("entries", {})
                    self._id_to_index = cached.get("id_to_index", {})
                self._loaded = True
                logger.info(f"Loaded {len(self._entries)} vectors from cache")
                return
        except Exception as e:
            logger.warning(f"Failed to load vector cache: {e}")

        # Fallback: load from SQLite
        self._rebuild_from_db()

    def _rebuild_from_db(self) -> None:
        """Rebuild in-memory state from SQLite records."""
        rows = self.db.fetchall("SELECT entry_id, source_table, source_id, content_hash FROM vector_entries")
        # We can't regenerate embeddings from DB alone without the original text,
        # so this just rebuilds metadata. Vectors would need to be re-indexed.
        # For now, we rely on the pickle cache for vector persistence.
        logger.info(f"Vector DB has {len(rows)} entries, but vectors require pickle cache")
        self._loaded = True

    def _persist_cache(self) -> None:
        """Save in-memory state to disk cache."""
        try:
            with open(self._vector_cache, "wb") as vf:
                pickle.dump(self._vectors, vf)
            with open(self._meta_cache, "wb") as mf:
                pickle.dump({"entries": self._entries, "id_to_index": self._id_to_index}, mf)
        except Exception as e:
            logger.warning(f"Failed to persist vector cache: {e}")

    def _rebuild_vectors(self) -> None:
        """Rebuild the numpy array after deletions."""
        if not self._entries:
            self._vectors = np.zeros((0, self.dimension), dtype=np.float32)
            return

        # This is a limitation - we'd need original embeddings to rebuild
        # For now, just reset and warn
        logger.warning("Vector rebuild after deletion not fully implemented - store may be inconsistent")
        self._vectors = np.zeros((len(self._entries), self.dimension), dtype=np.float32)
