"""
ChromaDB vector store wrapper for legal document chunks.

Provides a clean interface to:
  - Initialize a persistent or in-memory ChromaDB client
  - Insert document chunks with embeddings and metadata
  - Perform k-NN similarity search against a user query

Usage::

    from legal_doc_ingestion.vectorization import (
        ChromaVectorStore, LegalSemanticChunker, EmbeddingEngine,
    )

    store = ChromaVectorStore(persist_directory="./chroma_db")
    engine = EmbeddingEngine()
    chunker = LegalSemanticChunker()

    chunks = chunker.chunk(cleaned_text, source_id="contract.pdf")
    store.insert_chunks(chunks, engine)
    results = store.search("kira bedeli artış oranı", engine, k=5)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Union

from legal_doc_ingestion.vectorization.chunker import TextChunk

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """A single result from a similarity search."""

    chunk_id: str
    text: str
    distance: float
    source_id: str = ""
    section_heading: Optional[str] = None
    page_number: int = 1
    metadata: Dict[str, Any] = field(default_factory=dict)


class ChromaVectorStore:
    """
    High-level wrapper around ChromaDB for storing and querying
    legal document embeddings.

    Parameters
    ----------
    collection_name : str
        Name of the ChromaDB collection.
    persist_directory : str or None
        Directory for persistent storage. If None, uses in-memory mode.
    distance_metric : str
        Distance function: ``"cosine"``, ``"l2"``, or ``"ip"`` (inner product).
    """

    def __init__(
        self,
        *,
        collection_name: str = "legal_documents",
        persist_directory: Optional[str] = None,
        distance_metric: str = "cosine",
    ) -> None:
        self._collection_name = collection_name
        self._persist_dir = persist_directory
        self._distance_metric = distance_metric
        self._client = None  # lazy
        self._collection = None  # lazy

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def collection_name(self) -> str:
        return self._collection_name

    @property
    def count(self) -> int:
        """Number of documents currently in the collection."""
        return self._get_collection().count()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def insert_chunks(
        self,
        chunks: Sequence[TextChunk],
        embedding_engine: Any,
        *,
        batch_size: int = 100,
    ) -> int:
        """
        Embed and insert chunks into the vector store.

        Parameters
        ----------
        chunks : list[TextChunk]
            Chunks produced by LegalSemanticChunker.
        embedding_engine : EmbeddingEngine
            Engine used to generate embeddings.
        batch_size : int
            ChromaDB upsert batch size.

        Returns
        -------
        int
            Number of chunks inserted.
        """
        if not chunks:
            return 0

        collection = self._get_collection()

        # Extract texts and generate embeddings (multithreaded)
        texts = [c.text for c in chunks]
        logger.info("Generating embeddings for %d chunks…", len(texts))
        embeddings = embedding_engine.embed_batch(texts)

        # Prepare ChromaDB documents
        ids: List[str] = []
        documents: List[str] = []
        metadatas: List[Dict[str, Any]] = []
        embedding_list: List[List[float]] = []

        for chunk, emb in zip(chunks, embeddings):
            ids.append(chunk.chunk_id)
            documents.append(chunk.text)
            meta: Dict[str, Any] = {
                "source_id": chunk.source_id,
                "chunk_index": chunk.chunk_index,
                "total_chunks": chunk.total_chunks,
                "char_count": chunk.char_count,
                "page_number": chunk.page_number,
            }
            if chunk.section_heading:
                meta["section_heading"] = chunk.section_heading
            meta.update(chunk.metadata)
            metadatas.append(meta)
            embedding_list.append(emb)

        # Upsert in batches
        inserted = 0
        for start in range(0, len(ids), batch_size):
            end = min(start + batch_size, len(ids))
            collection.upsert(
                ids=ids[start:end],
                documents=documents[start:end],
                metadatas=metadatas[start:end],
                embeddings=embedding_list[start:end],
            )
            inserted += end - start
            logger.debug("Upserted batch %d–%d", start, end)

        logger.info(
            "Inserted %d chunks into collection '%s' (total: %d)",
            inserted, self._collection_name, collection.count(),
        )
        return inserted

    def search(
        self,
        query: str,
        embedding_engine: Any,
        *,
        k: int = 5,
        where: Optional[Dict[str, Any]] = None,
        source_filter: Optional[Union[str, List[str]]] = None,
    ) -> List[SearchResult]:
        """
        Perform k-NN similarity search.

        Parameters
        ----------
        query : str
            Natural language query text.
        embedding_engine : EmbeddingEngine
            Engine to embed the query.
        k : int
            Number of nearest neighbors to return.
        where : dict, optional
            ChromaDB metadata filter (e.g. ``{"source_id": "contract.pdf"}``).
        source_filter : str or list[str], optional
            Shorthand to filter by source_id.

        Returns
        -------
        list[SearchResult]
            Ordered by ascending distance (most similar first).
        """
        collection = self._get_collection()

        query_embedding = embedding_engine.embed(query)

        # Build filter
        chroma_where = where
        if source_filter and not chroma_where:
            if isinstance(source_filter, list):
                if len(source_filter) == 1:
                    chroma_where = {"source_id": source_filter[0]}
                else:
                    chroma_where = {"source_id": {"$in": source_filter}}
            else:
                chroma_where = {"source_id": source_filter}

        kwargs: Dict[str, Any] = {
            "query_embeddings": [query_embedding],
            "n_results": min(k, max(collection.count(), 1)),
            "include": ["documents", "metadatas", "distances"],
        }
        if chroma_where:
            kwargs["where"] = chroma_where

        raw = collection.query(**kwargs)

        results: List[SearchResult] = []
        if raw["ids"] and raw["ids"][0]:
            for i, chunk_id in enumerate(raw["ids"][0]):
                meta = raw["metadatas"][0][i] if raw["metadatas"] else {}
                results.append(
                    SearchResult(
                        chunk_id=chunk_id,
                        text=raw["documents"][0][i] if raw["documents"] else "",
                        distance=raw["distances"][0][i] if raw["distances"] else 0.0,
                        source_id=meta.get("source_id", ""),
                        section_heading=meta.get("section_heading"),
                        page_number=meta.get("page_number", 1),
                        metadata=meta,
                    )
                )

        return results

    def get_all(
        self,
        *,
        where: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
        include: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Fetch raw records (documents + metadata) from the collection without
        a similarity query.  Thin wrapper over ChromaDB's ``collection.get``
        so callers don't need to reach into the private collection object.

        Parameters
        ----------
        where : dict, optional
            Metadata filter (e.g. ``{"source_id": "contract.pdf"}``).
        limit : int, optional
            Maximum number of records to return.
        include : list[str], optional
            Fields to include (default: ``["documents", "metadatas"]``).
        """
        collection = self._get_collection()
        kwargs: Dict[str, Any] = {
            "include": include or ["documents", "metadatas"],
        }
        if where:
            kwargs["where"] = where
        if limit is not None:
            kwargs["limit"] = limit
        return collection.get(**kwargs)

    def get_source_metadata(self, source_id: str) -> Optional[Dict[str, Any]]:
        """Return the metadata of the first chunk for ``source_id`` (or None)."""
        raw = self.get_all(
            where={"source_id": source_id}, limit=1, include=["metadatas"]
        )
        metas = raw.get("metadatas") or []
        return metas[0] if metas else None

    def delete_by_source(self, source_id: str) -> None:
        """Remove all chunks belonging to a specific source document."""
        collection = self._get_collection()
        collection.delete(where={"source_id": source_id})
        logger.info("Deleted chunks for source_id='%s'", source_id)

    def reset_collection(self) -> None:
        """Drop and recreate the collection."""
        client = self._get_client()
        try:
            client.delete_collection(self._collection_name)
        except Exception:
            pass
        self._collection = None
        self._get_collection()
        logger.info("Collection '%s' reset.", self._collection_name)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _get_client(self):  # type: ignore[no-untyped-def]
        if self._client is None:
            try:
                import chromadb
            except ImportError as exc:
                raise ImportError(
                    "chromadb is required. Install: pip install chromadb"
                ) from exc

            if self._persist_dir:
                logger.info("ChromaDB persistent client at '%s'", self._persist_dir)
                self._client = chromadb.PersistentClient(path=self._persist_dir)
            else:
                logger.info("ChromaDB in-memory client")
                self._client = chromadb.Client()
        return self._client

    def _get_collection(self):  # type: ignore[no-untyped-def]
        if self._collection is None:
            client = self._get_client()
            self._collection = client.get_or_create_collection(
                name=self._collection_name,
                metadata={"hnsw:space": self._distance_metric},
            )
        return self._collection
