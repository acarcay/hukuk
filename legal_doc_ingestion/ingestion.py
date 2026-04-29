"""
Main orchestrator for the legal document ingestion pipeline.

Usage::

    from legal_doc_ingestion import LegalDocumentIngestor

    ingestor = LegalDocumentIngestor()

    # Single file
    result = ingestor.ingest("contract.pdf")
    print(result.to_json())

    # Batch
    results = ingestor.ingest_batch(["a.pdf", "b.docx", "c.rtf"])
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Union

from legal_doc_ingestion.cleaning import TextCleaner
from legal_doc_ingestion.exceptions import (
    CorruptedFileError,
    IngestionError,
    UnsupportedFormatError,
)
from legal_doc_ingestion.models import (
    DocumentMetadata,
    DocumentResult,
    DocumentType,
    PageContent,
)
from legal_doc_ingestion.parsers.base import BaseParser, RawDocument
from legal_doc_ingestion.parsers.docx_parser import DOCXParser
from legal_doc_ingestion.parsers.pdf_parser import PDFParser
from legal_doc_ingestion.parsers.rtf_parser import RTFParser

logger = logging.getLogger(__name__)

# Map of file extension → DocumentType enum
_EXT_TO_DOCTYPE: Dict[str, DocumentType] = {
    ".pdf": DocumentType.PDF,
    ".docx": DocumentType.DOCX,
    ".rtf": DocumentType.RTF,
}


class LegalDocumentIngestor:
    """
    High-level façade that routes files to the correct parser,
    cleans the extracted text, and produces structured ``DocumentResult`` objects.

    Parameters
    ----------
    cleaner
        Custom ``TextCleaner`` instance. If ``None``, a default cleaner is used.
    ocr_language
        Tesseract language code(s) forwarded to the PDF parser, e.g. ``"tur+eng"``.
    ocr_threshold
        Minimum character count per page before OCR is triggered for PDFs.
    extra_watermarks
        Additional watermark patterns passed to the text cleaner.
    """

    def __init__(
        self,
        *,
        cleaner: Optional[TextCleaner] = None,
        ocr_language: str = "tur+eng",
        ocr_threshold: int = 30,
        extra_watermarks: Optional[List[str]] = None,
    ) -> None:
        self._cleaner = cleaner or TextCleaner(extra_watermarks=extra_watermarks)

        # Instantiate format parsers
        self._parsers: Dict[str, BaseParser] = {}
        pdf_parser = PDFParser(ocr_language=ocr_language, ocr_threshold=ocr_threshold)
        docx_parser = DOCXParser()
        rtf_parser = RTFParser()

        for parser in (pdf_parser, docx_parser, rtf_parser):
            for ext in parser.supported_extensions:
                self._parsers[ext] = parser

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ingest(self, filepath: Union[str, Path]) -> DocumentResult:
        """
        Ingest a single legal document and return a structured result.

        Parameters
        ----------
        filepath
            Path to the document file.

        Returns
        -------
        DocumentResult
            Structured output containing cleaned text and metadata.

        Raises
        ------
        UnsupportedFormatError
            If the file extension is not handled.
        CorruptedFileError
            If the file cannot be opened.
        ParsingError
            If content extraction fails.
        """
        path = Path(filepath).resolve()
        self._validate_file(path)

        ext = path.suffix.lower()
        parser = self._parsers.get(ext)
        if parser is None:
            raise UnsupportedFormatError(str(path), ext)

        doc_type = _EXT_TO_DOCTYPE.get(ext, DocumentType.PDF)

        logger.info("Ingesting %s (%s)", path.name, doc_type.value)

        # Parse raw content
        raw_doc: RawDocument = parser.parse(path)

        # Clean each page
        pages: List[PageContent] = []
        for raw_page in raw_doc.pages:
            cleaned = self._cleaner.clean(raw_page.text)
            pages.append(
                PageContent(
                    page_number=raw_page.page_number,
                    raw_text=raw_page.text,
                    cleaned_text=cleaned,
                    ocr_applied=raw_page.ocr_applied,
                    confidence=raw_page.ocr_confidence,
                )
            )

        # Build metadata
        metadata = DocumentMetadata(
            filename=path.name,
            filepath=str(path),
            document_type=doc_type,
            total_pages=len(pages),
            file_size_bytes=path.stat().st_size,
            author=raw_doc.author,
            title=raw_doc.title,
            creation_date=raw_doc.creation_date,
        )

        result = DocumentResult(
            metadata=metadata,
            pages=pages,
            warnings=raw_doc.warnings,
        )

        logger.info(
            "Successfully ingested %s — %d page(s), %d warning(s).",
            path.name,
            len(pages),
            len(raw_doc.warnings),
        )

        return result

    def ingest_batch(
        self,
        filepaths: Sequence[Union[str, Path]],
        *,
        skip_errors: bool = True,
    ) -> List[Union[DocumentResult, IngestionError]]:
        """
        Ingest multiple files. Returns a list of results in the same order.

        Parameters
        ----------
        filepaths
            Iterable of file paths to ingest.
        skip_errors
            If ``True``, failed files produce an ``IngestionError`` in the
            result list rather than raising. If ``False``, the first error
            is raised immediately.

        Returns
        -------
        list[DocumentResult | IngestionError]
            One entry per input file, either the result or the error.
        """
        results: List[Union[DocumentResult, IngestionError]] = []

        for fp in filepaths:
            try:
                results.append(self.ingest(fp))
            except IngestionError as exc:
                logger.warning("Failed to ingest %s: %s", fp, exc)
                if skip_errors:
                    results.append(exc)
                else:
                    raise

        return results

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register_parser(self, parser: BaseParser) -> None:
        """Register a custom parser for additional file formats."""
        for ext in parser.supported_extensions:
            self._parsers[ext] = parser
            logger.info("Registered custom parser for %s", ext)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_file(path: Path) -> None:
        """Verify the file exists and is readable."""
        if not path.exists():
            raise CorruptedFileError(str(path), reason="File does not exist.")
        if not path.is_file():
            raise CorruptedFileError(str(path), reason="Path is not a file.")
        if path.stat().st_size == 0:
            raise CorruptedFileError(str(path), reason="File is empty (0 bytes).")
