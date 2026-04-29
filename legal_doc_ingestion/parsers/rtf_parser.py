"""
RTF parser using the ``striprtf`` library.

RTF files do not have a native page-break concept that ``striprtf``
exposes, so the entire file is treated as a single logical page.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Set

from legal_doc_ingestion.exceptions import CorruptedFileError, ParsingError
from legal_doc_ingestion.parsers.base import BaseParser, RawDocument, RawPage

logger = logging.getLogger(__name__)


class RTFParser(BaseParser):
    """Extracts text from ``.rtf`` (Rich Text Format) files."""

    @property
    def supported_extensions(self) -> Set[str]:
        return {".rtf"}

    def parse(self, filepath: Path) -> RawDocument:
        try:
            from striprtf.striprtf import rtf_to_text
        except ImportError as exc:
            raise ImportError(
                "striprtf is required for RTF parsing. "
                "Install it with: pip install striprtf"
            ) from exc

        filepath = filepath.resolve()

        # ------------------------------------------------------------------
        # Read raw bytes and decode
        # ------------------------------------------------------------------
        try:
            raw_bytes = filepath.read_bytes()
        except OSError as exc:
            raise CorruptedFileError(str(filepath), reason=str(exc)) from exc

        # Try common encodings
        raw_text: Optional[str] = None
        for encoding in ("utf-8", "latin-1", "cp1254", "cp1252"):
            try:
                raw_text = raw_bytes.decode(encoding)
                break
            except (UnicodeDecodeError, ValueError):
                continue

        if raw_text is None:
            raise CorruptedFileError(
                str(filepath),
                reason="Could not decode file with any supported encoding.",
            )

        # ------------------------------------------------------------------
        # Strip RTF formatting
        # ------------------------------------------------------------------
        try:
            plain_text = rtf_to_text(raw_text)
        except Exception as exc:
            raise ParsingError(str(filepath), reason=f"RTF conversion failed: {exc}") from exc

        if not plain_text or not plain_text.strip():
            raise ParsingError(str(filepath), reason="RTF file contains no extractable text.")

        # ------------------------------------------------------------------
        # Attempt to split on form-feed characters (page breaks in some RTFs)
        # ------------------------------------------------------------------
        segments = plain_text.split("\f")
        segments = [s for s in segments if s.strip()]  # drop empties

        if not segments:
            segments = [plain_text]

        raw_doc = RawDocument()
        for idx, segment in enumerate(segments, start=1):
            raw_doc.pages.append(RawPage(page_number=idx, text=segment))

        return raw_doc
