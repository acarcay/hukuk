"""
Centralized configuration.

Settings are read from environment variables and an optional ``.env`` file
(via ``pydantic-settings``).  All values have sensible defaults so the app
runs out-of-the-box for local development.

Precedence (highest first): explicit env var → ``.env`` file → default.
"""

from __future__ import annotations

from typing import Annotated, List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings — reads from environment and ``.env``."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # -- Server --
    # Bind to loopback by default; override with API_HOST=0.0.0.0 to expose.
    HOST: str = Field(default="127.0.0.1", alias="API_HOST")
    PORT: int = Field(default=8000, alias="API_PORT")
    DEBUG: bool = Field(default=False, alias="API_DEBUG")

    # -- Auth --
    # When set, sensitive endpoints require an ``X-API-Key`` header matching
    # this value.  When empty (default), auth is DISABLED — intended only for
    # local development.  A warning is logged at startup if unset.
    API_KEY: str = Field(default="")

    # -- CORS --
    # Comma-separated list of allowed origins.  Defaults to common local dev
    # front-end ports.  Set CORS_ORIGINS="*" to allow all (credentials are
    # then automatically disabled — the browser forbids "*" + credentials).
    # NoDecode: disable pydantic-settings' default JSON parsing of env values
    # so a plain comma-separated string (or "*") is accepted; the validator
    # below turns it into a list.
    CORS_ORIGINS: Annotated[List[str], NoDecode] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://localhost:8080",
            "http://127.0.0.1:3000",
        ]
    )

    # -- File uploads --
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE_MB: int = 50
    ALLOWED_EXTENSIONS: Annotated[List[str], NoDecode] = Field(
        default_factory=lambda: [".pdf", ".docx", ".rtf"]
    )

    # -- Embedding model --
    EMBEDDING_MODEL: str = "paraphrase-multilingual-MiniLM-L12-v2"
    EMBEDDING_DEVICE: str = "cpu"

    # -- ChromaDB --
    CHROMA_PERSIST_DIR: str = "./chroma_db"
    CHROMA_COLLECTION: str = "legal_documents"

    # -- Chunking --
    CHUNK_OVERLAP: float = 0.10
    CHUNK_MIN_CHARS: int = 100
    CHUNK_MAX_CHARS: int = 3000

    # -- LLM (Ollama) --
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.1:8b"
    OLLAMA_TIMEOUT: int = 120

    # -- RAG --
    RAG_TOP_K: int = 8
    RAG_MAX_CONTEXT_CHARS: int = 16000

    # -- Audit log (KVKK access trail) --
    # File that the "legal_rag.access" logger writes to.  Set to "" to disable
    # file-based audit logging (records still go to stdout via the root logger).
    AUDIT_LOG_FILE: str = "logs/access.log"
    AUDIT_LOG_MAX_BYTES: int = 10 * 1024 * 1024  # 10 MB per file
    AUDIT_LOG_BACKUPS: int = 5

    # ------------------------------------------------------------------
    # Validators — allow comma-separated strings for list-typed env vars
    # ------------------------------------------------------------------

    @field_validator("CORS_ORIGINS", "ALLOWED_EXTENSIONS", mode="before")
    @classmethod
    def _split_csv(cls, value):
        """Accept ``"a,b,c"`` from env vars and turn it into a list."""
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @property
    def auth_enabled(self) -> bool:
        """True when an API key is configured and auth should be enforced."""
        return bool(self.API_KEY)

    @property
    def cors_allow_credentials(self) -> bool:
        """Credentials cannot be combined with a wildcard origin."""
        return "*" not in self.CORS_ORIGINS


settings = Settings()
