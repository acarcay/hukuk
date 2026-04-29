"""
Pydantic data models representing the structured output
of the legal document ingestion pipeline.
"""

from __future__ import annotations

import datetime
from enum import Enum
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class DocumentType(str, Enum):
    """Supported document formats."""

    PDF = "pdf"
    DOCX = "docx"
    RTF = "rtf"
    IMAGE = "image"  # For standalone image OCR


class PageContent(BaseModel):
    """Cleaned text content for a single logical page."""

    page_number: int = Field(..., ge=1, description="1-indexed page number")
    raw_text: str = Field(..., description="Original extracted text before cleaning")
    cleaned_text: str = Field(..., description="Text after cleaning pipeline")
    ocr_applied: bool = Field(
        default=False,
        description="Whether OCR was used for this page",
    )
    confidence: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="OCR confidence score (0-1), None if OCR was not used",
    )


class DocumentMetadata(BaseModel):
    """Metadata extracted from and about the source document."""

    filename: str = Field(..., description="Original filename including extension")
    filepath: str = Field(..., description="Absolute path to the source file")
    document_type: DocumentType = Field(..., description="Detected document type")
    total_pages: int = Field(..., ge=1, description="Total number of pages")
    file_size_bytes: int = Field(..., ge=0, description="File size in bytes")
    ingested_at: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc),
        description="UTC timestamp of ingestion",
    )
    author: Optional[str] = Field(default=None, description="Document author if available")
    title: Optional[str] = Field(default=None, description="Document title if available")
    creation_date: Optional[str] = Field(
        default=None,
        description="Document creation date string if available",
    )


class DocumentResult(BaseModel):
    """
    Top-level result object returned by the ingestion pipeline.

    Serialisable to JSON via `.model_dump_json(indent=2)`.
    """

    metadata: DocumentMetadata
    pages: List[PageContent] = Field(
        ...,
        min_length=1,
        description="Ordered list of page contents",
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Non-fatal warnings encountered during ingestion",
    )

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    @model_validator(mode="after")
    def _check_page_count_consistency(self) -> "DocumentResult":
        if len(self.pages) != self.metadata.total_pages:
            raise ValueError(
                f"Page count mismatch: metadata says {self.metadata.total_pages} "
                f"pages but {len(self.pages)} PageContent objects were provided."
            )
        return self

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------
    def full_cleaned_text(self, separator: str = "\n\n") -> str:
        """Return the concatenated cleaned text of all pages."""
        return separator.join(p.cleaned_text for p in self.pages)

    def to_json(self, indent: int = 2) -> str:
        """Serialize the result to a formatted JSON string."""
        return self.model_dump_json(indent=indent)
