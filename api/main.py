"""
Legal RAG API — FastAPI application entry point.

Run with:
    uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

Or:
    python -m api.main
"""

from __future__ import annotations

import logging
import sys
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.config import settings
from api.dependencies import services

# ------------------------------------------------------------------
# Logging configuration
# ------------------------------------------------------------------

LOG_FORMAT = (
    "%(asctime)s │ %(levelname)-8s │ %(name)-30s │ %(message)s"
)


def _configure_logging() -> None:
    """Set up structured logging for the application."""
    level = logging.DEBUG if settings.DEBUG else logging.INFO

    logging.basicConfig(
        level=level,
        format=LOG_FORMAT,
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
        force=True,
    )

    # Quiet noisy libraries
    for noisy in ("httpx", "httpcore", "chromadb", "urllib3", "sentence_transformers"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


_configure_logging()
logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Lifespan — startup / shutdown
# ------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Initialize services on startup, cleanup on shutdown."""
    logger.info("=" * 60)
    logger.info("Legal RAG API — Starting up")
    logger.info("=" * 60)

    # Initialize all shared services
    services.initialize()

    # Check Ollama connectivity
    llm_ok = await services.llm.health_check()
    if llm_ok:
        logger.info("✓ Ollama connection verified (model=%s)", settings.OLLAMA_MODEL)
    else:
        logger.warning(
            "⚠ Ollama not reachable at %s — /chat will fail until Ollama is running. "
            "Start it with: ollama serve && ollama pull %s",
            settings.OLLAMA_BASE_URL,
            settings.OLLAMA_MODEL,
        )

    logger.info("=" * 60)
    logger.info("API ready — http://%s:%d/docs", settings.HOST, settings.PORT)
    logger.info("=" * 60)

    yield  # Application runs here

    logger.info("Shutting down Legal RAG API…")
    if services.llm is not None:
        await services.llm.aclose()


# ------------------------------------------------------------------
# FastAPI application
# ------------------------------------------------------------------

app = FastAPI(
    title="Legal RAG API",
    description=(
        "A high-performance RESTful API for Retrieval-Augmented Generation "
        "over Turkish and English legal documents. Supports document upload, "
        "semantic chunking, multilingual embedding, ChromaDB storage, and "
        "streaming LLM generation with a Zero-Hallucination policy."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ------------------------------------------------------------------
# CORS
# ------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)

# ------------------------------------------------------------------
# Audit / access log (KVKK — Legal data access trail)
#
# A separate logger ("legal_rag.access") emits one structured line
# per request on sensitive endpoints.  Route this to a dedicated
# file handler (or a SIEM sink) in your logging config:
#
#   logging.getLogger("legal_rag.access").addHandler(FileHandler("access.log"))
#
# Fields logged per request:
#   event      — REQUEST | RESPONSE
#   method     — HTTP verb
#   path       — endpoint path (NO query string to avoid PII in logs)
#   client_ip  — caller's IP address
#   request_id — correlation ID (X-Request-ID header or auto-generated)
#   status     — HTTP response status code
#   elapsed_ms — wall-clock time for the full request
#
# Query content (legal document text, source_id) is intentionally NOT
# logged here to prevent personal-data leakage in access logs.
# ------------------------------------------------------------------

_access_logger = logging.getLogger("legal_rag.access")

# Endpoints that handle potentially sensitive legal content
_SENSITIVE_PATHS = {"/api/v1/upload", "/api/v1/chat", "/api/v1/documents"}


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log every request with timing; emit audit trail for sensitive endpoints."""
    import uuid as _uuid

    start = time.monotonic()
    request_id = request.headers.get("X-Request-ID") or _uuid.uuid4().hex[:12]
    client_ip = request.client.host if request.client else "unknown"
    path = request.url.path

    logger.info(
        "→ %s %s (client=%s, request_id=%s)",
        request.method, path, client_ip, request_id,
    )

    # KVKK audit entry — REQUEST phase
    is_sensitive = any(path.startswith(p) for p in _SENSITIVE_PATHS)
    if is_sensitive:
        _access_logger.info(
            "event=REQUEST method=%s path=%s client_ip=%s request_id=%s",
            request.method, path, client_ip, request_id,
        )

    try:
        response = await call_next(request)
    except Exception:
        logger.exception("Unhandled exception in %s %s", request.method, path)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    elapsed_ms = (time.monotonic() - start) * 1000
    logger.info(
        "← %s %s → %d (%.1f ms)",
        request.method, path, response.status_code, elapsed_ms,
    )

    # KVKK audit entry — RESPONSE phase
    if is_sensitive:
        _access_logger.info(
            "event=RESPONSE method=%s path=%s client_ip=%s request_id=%s "
            "status=%d elapsed_ms=%.1f",
            request.method, path, client_ip, request_id,
            response.status_code, elapsed_ms,
        )

    response.headers["X-Response-Time-Ms"] = f"{elapsed_ms:.1f}"
    response.headers["X-Request-ID"] = request_id
    return response


# ------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------

from api.routes.upload import router as upload_router  # noqa: E402
from api.routes.chat import router as chat_router      # noqa: E402

from fastapi.staticfiles import StaticFiles
from pathlib import Path

app.include_router(upload_router, prefix="/api/v1")
app.include_router(chat_router, prefix="/api/v1")

# Mount uploads directory for PDF retrieval
Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
app.mount("/api/v1/documents/files", StaticFiles(directory=settings.UPLOAD_DIR), name="documents_files")

# ------------------------------------------------------------------
# Health / status
# ------------------------------------------------------------------

@app.get("/health", tags=["System"])
async def health():
    """Health check endpoint."""
    llm_ok = await services.llm.health_check()
    return {
        "status": "healthy",
        "vector_store": {
            "collection": settings.CHROMA_COLLECTION,
            "document_count": services.store.count,
        },
        "llm": {
            "model": settings.OLLAMA_MODEL,
            "reachable": llm_ok,
        },
        "embedding_model": settings.EMBEDDING_MODEL,
    }


@app.get("/", tags=["System"])
async def root():
    """API root — redirect to docs."""
    return {
        "service": "Legal RAG API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }


# ------------------------------------------------------------------
# CLI entry point
# ------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="debug" if settings.DEBUG else "info",
    )
