"""
FastAPI dependency injection — shared singleton services.

These are initialized once at startup (via lifespan) and injected
into route handlers via ``Depends()``.
"""

from __future__ import annotations

import logging
from typing import Optional

from legal_doc_ingestion.ingestion import LegalDocumentIngestor
from legal_doc_ingestion.vectorization.chunker import LegalSemanticChunker
from legal_doc_ingestion.vectorization.embedder import EmbeddingEngine
from legal_doc_ingestion.vectorization.store import ChromaVectorStore

from api.config import settings
from api.llm import OllamaClient

logger = logging.getLogger(__name__)


class ServiceContainer:
    """
    Holds all shared service instances. Initialized once during
    the FastAPI lifespan and accessed via dependency injection.
    """

    def __init__(self) -> None:
        self.ingestor: Optional[LegalDocumentIngestor] = None
        self.chunker: Optional[LegalSemanticChunker] = None
        self.embedder: Optional[EmbeddingEngine] = None
        self.store: Optional[ChromaVectorStore] = None
        self.llm: Optional[OllamaClient] = None

    def initialize(self) -> None:
        """Eagerly create all service singletons."""
        logger.info("Initializing service container…")

        self.ingestor = LegalDocumentIngestor()
        logger.info("✓ Document ingestor ready")

        self.chunker = LegalSemanticChunker(
            overlap_ratio=settings.CHUNK_OVERLAP,
            min_chunk_chars=settings.CHUNK_MIN_CHARS,
            max_chunk_chars=settings.CHUNK_MAX_CHARS,
        )
        logger.info("✓ Semantic chunker ready (overlap=%.0f%%)", settings.CHUNK_OVERLAP * 100)

        self.embedder = EmbeddingEngine(
            model_name=settings.EMBEDDING_MODEL,
            device=settings.EMBEDDING_DEVICE,
        )
        logger.info("✓ Embedding engine ready (model=%s)", settings.EMBEDDING_MODEL)

        self.store = ChromaVectorStore(
            collection_name=settings.CHROMA_COLLECTION,
            persist_directory=settings.CHROMA_PERSIST_DIR,
        )
        logger.info(
            "✓ ChromaDB store ready (collection=%s, vectors=%d)",
            settings.CHROMA_COLLECTION,
            self.store.count,
        )

        self.llm = OllamaClient()
        logger.info("✓ Ollama LLM client ready (model=%s)", settings.OLLAMA_MODEL)


# Global singleton — populated during lifespan
services = ServiceContainer()
