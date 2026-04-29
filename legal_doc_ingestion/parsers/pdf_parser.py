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
    """

    def __init__(
        self,
        *,
        ocr_threshold: int = _MIN_TEXT_LENGTH,
        ocr_language: str = "tur+eng",
        dpi: int = 300,
    ) -> None:
        self._ocr_threshold = ocr_threshold
        self._ocr_language = ocr_language
        self._dpi = dpi

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

        try:
            for page_idx in range(len(doc)):
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
                        text, ocr_confidence = self._ocr_page(page)
                        ocr_applied = True
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
