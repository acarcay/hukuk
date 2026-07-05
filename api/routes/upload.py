"""
POST /upload — Accept document files and trigger the full
ingestion → chunking → embedding → ChromaDB pipeline.

Runs the CPU-heavy work in a thread pool so the event loop
stays responsive for other concurrent requests.
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from pathlib import Path
from typing import Dict, List

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from api.config import settings
from api.dependencies import services

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Documents"])


# ------------------------------------------------------------------
# Response schemas
# ------------------------------------------------------------------

class UploadResult(BaseModel):
    """Response for a single uploaded file."""

    filename: str
    source_id: str
    document_type: str
    total_pages: int
    chunks_created: int
    status: str = "success"
    warnings: List[str] = Field(default_factory=list)


class UploadResponse(BaseModel):
    """Aggregate response for the /upload endpoint."""

    message: str
    documents: List[UploadResult]
    total_chunks: int


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _ensure_upload_dir() -> Path:
    """Create upload directory if it doesn't exist."""
    upload_path = Path(settings.UPLOAD_DIR)
    upload_path.mkdir(parents=True, exist_ok=True)
    return upload_path


def _validate_extension(filename: str) -> str:
    """Validate file extension and return it."""
    ext = Path(filename).suffix.lower()
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. "
                   f"Allowed: {', '.join(settings.ALLOWED_EXTENSIONS)}",
        )
    return ext


def _process_document(filepath: Path, disk_filename: str) -> Dict:
    """
    Synchronous pipeline: ingest → chunk → embed → store.
    Called inside a thread pool to avoid blocking the event loop.

    ``disk_filename`` is the actual filename on disk (uuid-prefixed),
    stored as metadata so ``delete_document`` can locate the physical file.
    """
    # Step 1: Ingest (parse + clean)
    result = services.ingestor.ingest(filepath)
    cleaned_text = result.full_cleaned_text()

    # Step 1b: Remove any previously indexed chunks for this source so that
    # re-uploads of the same filename don't leave orphaned (stale) chunks.
    # Without this, upsert only overwrites chunks with the same chunk_id; if
    # the new version has *fewer* chunks, the extras from the old version
    # survive and contaminate search results with outdated legal text.
    source_id = result.metadata.filename
    try:
        services.store.delete_by_source(source_id)
    except Exception:
        pass  # collection may not exist yet on first upload

    # Calculate page boundaries
    page_boundaries = []
    current_len = 0
    for p in result.pages:
        current_len += len(p.cleaned_text) + 2  # +2 for "\n\n" separator
        page_boundaries.append((current_len, p.page_number))

    # Step 2: Semantic chunking
    chunks = services.chunker.chunk(
        cleaned_text,
        source_id=source_id,
        extra_metadata={
            "document_type": result.metadata.document_type.value,
            "total_pages": str(result.metadata.total_pages),
            # Store the real disk filename so DELETE can find the file
            "disk_filename": disk_filename,
        },
        page_boundaries=page_boundaries,
    )

    # Step 3: Embed + store in ChromaDB
    if chunks:
        services.store.insert_chunks(chunks, services.embedder)

    return {
        "filename": result.metadata.filename,
        "source_id": source_id,
        "disk_filename": disk_filename,
        "document_type": result.metadata.document_type.value,
        "total_pages": result.metadata.total_pages,
        "chunks_created": len(chunks),
        "warnings": result.warnings,
    }


# ------------------------------------------------------------------
# Endpoint
# ------------------------------------------------------------------

@router.post(
    "/upload",
    response_model=UploadResponse,
    summary="Upload and ingest legal documents",
    description=(
        "Accept one or more legal document files (PDF, DOCX, RTF), "
        "run the full ingestion pipeline (parse → clean → chunk → embed), "
        "and store the vectors in ChromaDB."
    ),
)
async def upload_documents(
    files: List[UploadFile] = File(
        ..., description="One or more legal document files"
    ),
) -> UploadResponse:
    """Handle document upload and ingestion."""
    if not files:
        raise HTTPException(status_code=400, detail="No files provided.")

    upload_dir = _ensure_upload_dir()
    results: List[UploadResult] = []
    total_chunks = 0
    loop = asyncio.get_event_loop()

    for upload_file in files:
        filename = upload_file.filename or f"unnamed_{uuid.uuid4().hex[:8]}"
        logger.info("Processing upload: %s", filename)

        # Validate extension
        _validate_extension(filename)

        # Save to disk
        safe_name = f"{uuid.uuid4().hex[:8]}_{filename}"
        filepath = upload_dir / safe_name

        try:
            content = await upload_file.read()

            # Check file size
            size_mb = len(content) / (1024 * 1024)
            if size_mb > settings.MAX_UPLOAD_SIZE_MB:
                raise HTTPException(
                    status_code=413,
                    detail=f"File '{filename}' exceeds {settings.MAX_UPLOAD_SIZE_MB}MB limit.",
                )

            filepath.write_bytes(content)
            logger.info("Saved %s (%.2f MB)", safe_name, size_mb)

            # Run CPU-heavy pipeline in thread pool
            doc_result = await loop.run_in_executor(
                None, _process_document, filepath, safe_name
            )

            results.append(UploadResult(**{k: v for k, v in doc_result.items() if k != "disk_filename"}))
            total_chunks += doc_result["chunks_created"]

        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("Failed to process %s", filename)
            results.append(
                UploadResult(
                    filename=filename,
                    source_id=filename,
                    document_type="unknown",
                    total_pages=0,
                    chunks_created=0,
                    status="error",
                    warnings=[str(exc)],
                )
            )
        finally:
            pass

    return UploadResponse(
        message=f"Processed {len(results)} document(s).",
        documents=results,
        total_chunks=total_chunks,
    )
