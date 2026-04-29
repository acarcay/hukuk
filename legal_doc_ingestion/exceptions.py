"""
Custom exception hierarchy for the legal document ingestion pipeline.

All exceptions inherit from IngestionError to allow broad or granular
exception handling by consumers of this module.
"""

from typing import Optional


class IngestionError(Exception):
    """Base exception for all ingestion-related errors."""

    def __init__(self, message: str, filepath: Optional[str] = None) -> None:
        self.filepath = filepath
        super().__init__(message)


class UnsupportedFormatError(IngestionError):
    """Raised when a file format is not supported by the ingestion pipeline."""

    def __init__(self, filepath: str, extension: str) -> None:
        self.extension = extension
        super().__init__(
            f"Unsupported file format '{extension}' for file: {filepath}",
            filepath=filepath,
        )


class CorruptedFileError(IngestionError):
    """Raised when a file cannot be opened or appears to be corrupted."""

    def __init__(self, filepath: str, reason: str = "") -> None:
        detail = f" — {reason}" if reason else ""
        super().__init__(
            f"Corrupted or unreadable file: {filepath}{detail}",
            filepath=filepath,
        )


class ParsingError(IngestionError):
    """Raised when parsing succeeds at opening the file but fails to extract content."""

    def __init__(self, filepath: str, page: Optional[int] = None, reason: str = "") -> None:
        self.page = page
        location = f" (page {page})" if page is not None else ""
        detail = f" — {reason}" if reason else ""
        super().__init__(
            f"Failed to parse content from {filepath}{location}{detail}",
            filepath=filepath,
        )


class OCRError(IngestionError):
    """Raised when OCR processing fails on a scanned document or image."""

    def __init__(self, filepath: str, reason: str = "") -> None:
        detail = f" — {reason}" if reason else ""
        super().__init__(
            f"OCR processing failed for {filepath}{detail}",
            filepath=filepath,
        )
