"""
PDF parser using PyMuPDF (fitz) with pytesseract OCR fallback
for scanned pages.
"""

from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import Optional, Set, Tuple, List, TYPE_CHECKING

from legal_doc_ingestion.exceptions import CorruptedFileError, OCRError, ParsingError
from legal_doc_ingestion.parsers.base import BaseParser, RawDocument, RawPage

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Minimum character count to consider a page as "text-based" (not scanned)
_MIN_TEXT_LENGTH = 30


class PDFParser(BaseParser):
    """
    Extracts text from PDF files using PyMuPDF.

    If a page yields fewer than ``ocr_threshold`` characters,
    the parser renders the page as an image and applies OCR
    via pytesseract.

    Parameters
    ----------
    ocr_threshold
        Minimum character count per page before OCR is triggered.
    ocr_language
        Tesseract language code(s), e.g. ``"tur+eng"`` for Turkish + English.
    dpi
        Resolution used when rendering pages to images for OCR.
    max_pages
        Hard upper limit on pages processed.  Documents exceeding this will
        be partially ingested with a warning.  Prevents decompression-bomb
        style DoS from very large scanned PDFs (default: 200).
    ocr_timeout_seconds
        Per-page OCR time limit in seconds.  If OCR takes longer the page
        is skipped and a warning is added.  ``0`` disables the timeout.
    """

    def __init__(
        self,
        *,
        ocr_threshold: int = _MIN_TEXT_LENGTH,
        ocr_language: str = "tur+eng",
        dpi: int = 300,
        max_pages: int = 200,
        ocr_timeout_seconds: int = 30,
    ) -> None:
        self._ocr_threshold = ocr_threshold
        self._ocr_language = ocr_language
        self._dpi = dpi
        self._max_pages = max_pages
        self._ocr_timeout = ocr_timeout_seconds

    # ------------------------------------------------------------------
    # BaseParser interface
    # ------------------------------------------------------------------

    @property
    def supported_extensions(self) -> Set[str]:
        return {".pdf"}

    def parse(self, filepath: Path) -> RawDocument:
        try:
            import fitz  # PyMuPDF
        except ImportError as exc:
            raise ImportError(
                "PyMuPDF is required for PDF parsing. "
                "Install it with: pip install PyMuPDF"
            ) from exc

        filepath = filepath.resolve()

        try:
            doc = fitz.open(str(filepath))
        except Exception as exc:
            raise CorruptedFileError(str(filepath), reason=str(exc)) from exc

        raw_doc = RawDocument(
            author=doc.metadata.get("author") if doc.metadata else None,
            title=doc.metadata.get("title") if doc.metadata else None,
            creation_date=doc.metadata.get("creationDate") if doc.metadata else None,
        )

        total_pages = len(doc)

        # Guard: cap the number of pages processed to avoid DoS from huge
        # scanned PDFs that would monopolise the OCR worker thread.
        if total_pages > self._max_pages:
            raw_doc.warnings.append(
                f"Document has {total_pages} pages but only the first "
                f"{self._max_pages} will be processed (max_pages={self._max_pages})."
            )
            logger.warning(
                "PDF '%s' has %d pages; capping at %d.",
                filepath.name, total_pages, self._max_pages,
            )

        pages_to_process = min(total_pages, self._max_pages)

        try:
            for page_idx in range(pages_to_process):
                page = doc[page_idx]
                page_num = page_idx + 1

                try:
                    text = page.get_text("text") or ""
                except Exception as exc:
                    raw_doc.warnings.append(
                        f"Page {page_num}: text extraction failed ({exc}), "
                        f"attempting OCR."
                    )
                    text = ""

                ocr_applied = False
                ocr_confidence: Optional[float] = None

                # Fallback to OCR when text is sparse
                if len(text.strip()) < self._ocr_threshold:
                    logger.info(
                        "Page %d has sparse text (%d chars), applying OCR.",
                        page_num,
                        len(text.strip()),
                    )
                    try:
                        text, ocr_confidence = self._ocr_page_with_timeout(page, page_num, raw_doc)
                        ocr_applied = text != ""
                    except OCRError as exc:
                        raw_doc.warnings.append(
                            f"Page {page_num}: OCR failed — {exc}"
                        )
                        # Keep whatever text we extracted, even if sparse

                raw_doc.pages.append(
                    RawPage(
                        page_number=page_num,
                        text=text,
                        ocr_applied=ocr_applied,
                        ocr_confidence=ocr_confidence,
                    )
                )
        except Exception as exc:
            if not raw_doc.pages:
                raise ParsingError(str(filepath), reason=str(exc)) from exc
            raw_doc.warnings.append(f"Parsing stopped early: {exc}")
        finally:
            doc.close()

        if not raw_doc.pages:
            raise ParsingError(str(filepath), reason="No pages could be extracted.")

        return raw_doc

    # ------------------------------------------------------------------
    # OCR internals
    # ------------------------------------------------------------------

    def _ocr_page_with_timeout(
        self,
        page,  # type: ignore[no-untyped-def]
        page_num: int,
        raw_doc: RawDocument,
    ) -> Tuple[str, Optional[float]]:
        """
        Run ``_ocr_page`` with a per-page wall-clock timeout.

        Uses a daemon thread so that even if Tesseract hangs, it won't
        prevent the main process from continuing.  On timeout the page
        is skipped and an empty string is returned.
        """
        import concurrent.futures

        if self._ocr_timeout <= 0:
            return self._ocr_page(page)

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(self._ocr_page, page)
            try:
                return future.result(timeout=self._ocr_timeout)
            except concurrent.futures.TimeoutError:
                raw_doc.warnings.append(
                    f"Page {page_num}: OCR timed out after {self._ocr_timeout}s — page skipped."
                )
                logger.warning(
                    "OCR timeout on page %d of document (limit=%ds).",
                    page_num, self._ocr_timeout,
                )
                return "", None

    def _ocr_page(self, page) -> Tuple[str, Optional[float]]:  # type: ignore[no-untyped-def]
        """Render a PyMuPDF page to an image and run pytesseract OCR."""
        try:
            import pytesseract
            from PIL import Image
        except ImportError as exc:
            raise OCRError(
                "N/A",
                reason="pytesseract and Pillow are required for OCR. "
                "Install with: pip install pytesseract Pillow",
            ) from exc

        try:
            # Render page at the configured DPI
            zoom = self._dpi / 72  # 72 is the default PDF DPI
            matrix = __import__("fitz").Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=matrix)

            img = Image.open(io.BytesIO(pix.tobytes("png")))

            # Run OCR — also get per-word confidence data
            ocr_data = pytesseract.image_to_data(
                img, lang=self._ocr_language, output_type=pytesseract.Output.DICT
            )

            words: List[str] = []
            confidences: List[int] = []
            for word, conf in zip(ocr_data["text"], ocr_data["conf"]):
                word = word.strip()
                if word:
                    words.append(word)
                    if isinstance(conf, int) and conf >= 0:
                        confidences.append(conf)

            text = " ".join(words)
            avg_confidence = (
                round(sum(confidences) / len(confidences) / 100, 4)
                if confidences
                else None
            )

            return text, avg_confidence

        except pytesseract.TesseractNotFoundError as exc:
            raise OCRError(
                "N/A",
                reason="Tesseract is not installed or not in PATH.",
            ) from exc
        except Exception as exc:
            raise OCRError("N/A", reason=str(exc)) from exc
