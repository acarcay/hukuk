"""
Vectorization sub-package for the legal document ingestion pipeline.

Provides semantic chunking, embedding generation, and ChromaDB
vector store integration tailored for legal documents.
"""

from legal_doc_ingestion.vectorization.chunker import (
    LegalSemanticChunker,
    TextChunk,
)
from legal_doc_ingestion.vectorization.embedder import EmbeddingEngine
from legal_doc_ingestion.vectorization.store import ChromaVectorStore, SearchResult

__all__ = [
    "LegalSemanticChunker",
    "TextChunk",
    "EmbeddingEngine",
    "ChromaVectorStore",
    "SearchResult",
]
