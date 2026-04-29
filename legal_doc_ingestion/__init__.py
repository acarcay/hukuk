"""
Legal Document Ingestion Module
================================
A robust Python module for parsing, cleaning, and structuring
legal documents from PDF, DOCX, and RTF formats.

Supports OCR fallback for scanned PDFs and images via pytesseract.
"""

from legal_doc_ingestion.models import (
    DocumentResult,
    PageContent,
    DocumentMetadata,
    DocumentType,
)
from legal_doc_ingestion.ingestion import LegalDocumentIngestor
from legal_doc_ingestion.cleaning import TextCleaner
from legal_doc_ingestion.exceptions import (
    IngestionError,
    UnsupportedFormatError,
    CorruptedFileError,
    OCRError,
    ParsingError,
)
from legal_doc_ingestion.vectorization import (
    LegalSemanticChunker,
    TextChunk,
    EmbeddingEngine,
    ChromaVectorStore,
    SearchResult,
)

__all__ = [
    "LegalDocumentIngestor",
    "TextCleaner",
    "DocumentResult",
    "PageContent",
    "DocumentMetadata",
    "DocumentType",
    "IngestionError",
    "UnsupportedFormatError",
    "CorruptedFileError",
    "OCRError",
    "ParsingError",
    # Vectorization pipeline
    "LegalSemanticChunker",
    "TextChunk",
    "EmbeddingEngine",
    "ChromaVectorStore",
    "SearchResult",
]

__version__ = "2.0.0"

