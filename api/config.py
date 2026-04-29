"""
Centralized configuration via environment variables with sensible defaults.

All settings can be overridden via env vars or a ``.env`` file.
"""

from __future__ import annotations

import os
from typing import List, Optional


class Settings:
    """Application settings — reads from environment with defaults."""

    # -- Server --
    HOST: str = os.getenv("API_HOST", "0.0.0.0")
    PORT: int = int(os.getenv("API_PORT", "8000"))
    DEBUG: bool = os.getenv("API_DEBUG", "false").lower() == "true"

    # -- CORS --
    CORS_ORIGINS: List[str] = os.getenv(
        "CORS_ORIGINS", "http://localhost:3000,http://localhost:5173"
    ).split(",")

    # -- File uploads --
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "./uploads")
    MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "50"))
    ALLOWED_EXTENSIONS: List[str] = [".pdf", ".docx", ".rtf"]

    # -- Embedding model --
    EMBEDDING_MODEL: str = os.getenv(
        "EMBEDDING_MODEL", "paraphrase-multilingual-MiniLM-L12-v2"
    )
    EMBEDDING_DEVICE: str = os.getenv("EMBEDDING_DEVICE", "cpu")

    # -- ChromaDB --
    CHROMA_PERSIST_DIR: str = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
    CHROMA_COLLECTION: str = os.getenv("CHROMA_COLLECTION", "legal_documents")

    # -- Chunking --
    CHUNK_OVERLAP: float = float(os.getenv("CHUNK_OVERLAP", "0.10"))
    CHUNK_MIN_CHARS: int = int(os.getenv("CHUNK_MIN_CHARS", "100"))
    CHUNK_MAX_CHARS: int = int(os.getenv("CHUNK_MAX_CHARS", "3000"))

    # -- LLM (Ollama) --
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3:8b")
    OLLAMA_TIMEOUT: int = int(os.getenv("OLLAMA_TIMEOUT", "120"))

    # -- RAG --
    RAG_TOP_K: int = int(os.getenv("RAG_TOP_K", "5"))
    RAG_MAX_CONTEXT_CHARS: int = int(os.getenv("RAG_MAX_CONTEXT_CHARS", "6000"))


settings = Settings()
