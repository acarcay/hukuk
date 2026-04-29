"""
Unit tests for the legal document ingestion module.

Run with: pytest tests/ -v
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from legal_doc_ingestion.cleaning import TextCleaner
from legal_doc_ingestion.exceptions import (
    CorruptedFileError,
    IngestionError,
    UnsupportedFormatError,
)
from legal_doc_ingestion.ingestion import LegalDocumentIngestor
from legal_doc_ingestion.models import DocumentResult, DocumentType, PageContent


# ======================================================================
# Text Cleaner Tests
# ======================================================================


class TestTextCleaner:
    """Tests for the TextCleaner utility."""

    def setup_method(self) -> None:
        self.cleaner = TextCleaner()

    def test_removes_watermark_lines(self) -> None:
        text = "Line one\nCONFIDENTIAL\nLine two\nDRAFT\nLine three"
        result = self.cleaner.clean(text)
        assert "CONFIDENTIAL" not in result
        assert "DRAFT" not in result
        assert "Line one" in result
        assert "Line two" in result
        assert "Line three" in result

    def test_removes_page_numbers_bare(self) -> None:
        text = "Some legal text.\n\n  42  \n\nMore text follows."
        result = self.cleaner.clean(text)
        assert "42" not in result
        assert "Some legal text." in result
        assert "More text follows." in result

    def test_removes_page_of_pattern(self) -> None:
        text = "Content here.\nPage 3 of 10\nMore content."
        result = self.cleaner.clean(text)
        assert "Page 3 of 10" not in result

    def test_removes_dash_page_numbers(self) -> None:
        text = "Text above.\n- 7 -\nText below."
        result = self.cleaner.clean(text)
        assert "- 7 -" not in result

    def test_collapses_excessive_newlines(self) -> None:
        text = "Para one.\n\n\n\n\nPara two."
        result = self.cleaner.clean(text)
        # Should have at most 2 consecutive newlines
        assert "\n\n\n" not in result
        assert "Para one." in result
        assert "Para two." in result

    def test_normalizes_smart_quotes(self) -> None:
        text = "\u201cHello\u201d and \u2018world\u2019"
        result = self.cleaner.clean(text)
        assert '"Hello"' in result
        assert "'world'" in result

    def test_removes_null_bytes(self) -> None:
        text = "Clean\x00 text\x00 here"
        result = self.cleaner.clean(text)
        assert "\x00" not in result
        assert "Clean text here" in result

    def test_strips_stray_urls(self) -> None:
        text = "Content\nhttps://www.example.com/footer\nMore content"
        result = self.cleaner.clean(text)
        assert "https://www.example.com" not in result

    def test_custom_watermark(self) -> None:
        cleaner = TextCleaner(extra_watermarks=[r"TASLAK"])
        text = "Madde 1.\nTASLAK\nMadde 2."
        result = cleaner.clean(text)
        assert "TASLAK" not in result

    def test_preserves_inline_watermark_words(self) -> None:
        """Watermark removal only strips lines that *solely* match the pattern."""
        text = "This is a confidential agreement between the parties."
        result = self.cleaner.clean(text)
        # The full line does NOT match the watermark pattern (fullmatch), so it stays
        assert "confidential agreement" in result

    def test_custom_step_insertion(self) -> None:
        def upper(text: str) -> str:
            return text.upper()

        self.cleaner.add_step("uppercase", upper)
        result = self.cleaner.clean("hello world")
        assert result == "HELLO WORLD"

    def test_turkish_page_number_pattern(self) -> None:
        text = "İçerik\nSayfa 3/10\nDevam"
        result = self.cleaner.clean(text)
        assert "Sayfa 3/10" not in result


# ======================================================================
# Model Tests
# ======================================================================


class TestModels:
    """Tests for Pydantic data models."""

    def test_document_result_serialization(self) -> None:
        from legal_doc_ingestion.models import DocumentMetadata

        metadata = DocumentMetadata(
            filename="test.pdf",
            filepath="/tmp/test.pdf",
            document_type=DocumentType.PDF,
            total_pages=1,
            file_size_bytes=1024,
        )
        page = PageContent(
            page_number=1,
            raw_text="Raw text",
            cleaned_text="Clean text",
        )
        result = DocumentResult(metadata=metadata, pages=[page])

        json_str = result.to_json()
        parsed = json.loads(json_str)

        assert parsed["metadata"]["filename"] == "test.pdf"
        assert parsed["metadata"]["document_type"] == "pdf"
        assert len(parsed["pages"]) == 1
        assert parsed["pages"][0]["cleaned_text"] == "Clean text"

    def test_page_count_mismatch_raises(self) -> None:
        from legal_doc_ingestion.models import DocumentMetadata

        metadata = DocumentMetadata(
            filename="test.pdf",
            filepath="/tmp/test.pdf",
            document_type=DocumentType.PDF,
            total_pages=5,  # mismatch!
            file_size_bytes=1024,
        )
        page = PageContent(
            page_number=1,
            raw_text="text",
            cleaned_text="text",
        )
        with pytest.raises(ValueError, match="Page count mismatch"):
            DocumentResult(metadata=metadata, pages=[page])

    def test_full_cleaned_text_concatenation(self) -> None:
        from legal_doc_ingestion.models import DocumentMetadata

        metadata = DocumentMetadata(
            filename="test.pdf",
            filepath="/tmp/test.pdf",
            document_type=DocumentType.PDF,
            total_pages=2,
            file_size_bytes=100,
        )
        pages = [
            PageContent(page_number=1, raw_text="A", cleaned_text="Page A"),
            PageContent(page_number=2, raw_text="B", cleaned_text="Page B"),
        ]
        result = DocumentResult(metadata=metadata, pages=pages)
        assert result.full_cleaned_text() == "Page A\n\nPage B"
        assert result.full_cleaned_text(separator=" | ") == "Page A | Page B"


# ======================================================================
# Ingestor Validation Tests
# ======================================================================


class TestIngestorValidation:
    """Tests for the LegalDocumentIngestor input validation."""

    def setup_method(self) -> None:
        self.ingestor = LegalDocumentIngestor()

    def test_nonexistent_file_raises_corrupted_error(self) -> None:
        with pytest.raises(CorruptedFileError, match="does not exist"):
            self.ingestor.ingest("/nonexistent/file.pdf")

    def test_empty_file_raises_corrupted_error(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"")  # 0 bytes
            path = f.name

        with pytest.raises(CorruptedFileError, match="empty"):
            self.ingestor.ingest(path)

        Path(path).unlink(missing_ok=True)

    def test_unsupported_extension_raises(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".xyz", delete=False) as f:
            f.write(b"some content")
            path = f.name

        with pytest.raises(UnsupportedFormatError, match=".xyz"):
            self.ingestor.ingest(path)

        Path(path).unlink(missing_ok=True)

    def test_batch_skip_errors(self) -> None:
        """Batch ingestion with skip_errors=True should not raise."""
        results = self.ingestor.ingest_batch(
            ["/nonexistent/a.pdf", "/nonexistent/b.docx"],
            skip_errors=True,
        )
        assert len(results) == 2
        assert all(isinstance(r, IngestionError) for r in results)


# ======================================================================
# DOCX Parser Integration Test
# ======================================================================


class TestDocxParsing:
    """Integration test for DOCX parsing (requires python-docx)."""

    def test_parse_simple_docx(self) -> None:
        """Create a minimal DOCX in-memory and parse it."""
        try:
            from docx import Document as DocxDocument
        except ImportError:
            pytest.skip("python-docx not installed")

        # Create a test DOCX
        doc = DocxDocument()
        doc.add_paragraph("MADDE 1 — Taraflar")
        doc.add_paragraph("Bu sözleşme aşağıdaki taraflar arasında imzalanmıştır.")
        doc.add_paragraph("MADDE 2 — Konu")
        doc.add_paragraph("Sözleşmenin konusu aşağıda belirtilmiştir.")

        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
            doc.save(f.name)
            path = f.name

        try:
            ingestor = LegalDocumentIngestor()
            result = ingestor.ingest(path)

            assert result.metadata.document_type == DocumentType.DOCX
            assert result.metadata.filename.endswith(".docx")
            assert len(result.pages) >= 1
            assert "MADDE 1" in result.full_cleaned_text()
            assert "Taraflar" in result.full_cleaned_text()

            # Verify JSON serialization round-trip
            json_str = result.to_json()
            parsed = json.loads(json_str)
            assert "metadata" in parsed
            assert "pages" in parsed
        finally:
            Path(path).unlink(missing_ok=True)


# ======================================================================
# RTF Parser Integration Test
# ======================================================================


class TestRtfParsing:
    """Integration test for RTF parsing (requires striprtf)."""

    def test_parse_simple_rtf(self) -> None:
        try:
            from striprtf.striprtf import rtf_to_text  # noqa: F401
        except ImportError:
            pytest.skip("striprtf not installed")

        rtf_content = (
            r"{\rtf1\ansi\deff0"
            r"{\fonttbl{\f0 Times New Roman;}}"
            r"\pard Madde 1 - Taraflar\par"
            r"\pard Bu sozlesme asagidaki taraflar arasinda imzalanmistir.\par"
            r"}"
        )

        with tempfile.NamedTemporaryFile(
            suffix=".rtf", delete=False, mode="w", encoding="utf-8"
        ) as f:
            f.write(rtf_content)
            path = f.name

        try:
            ingestor = LegalDocumentIngestor()
            result = ingestor.ingest(path)

            assert result.metadata.document_type == DocumentType.RTF
            assert len(result.pages) >= 1
            assert "Madde 1" in result.full_cleaned_text()
        finally:
            Path(path).unlink(missing_ok=True)


# ======================================================================
# Exception Hierarchy Tests
# ======================================================================


class TestExceptionHierarchy:
    """Verify that all custom exceptions inherit from IngestionError."""

    def test_all_exceptions_are_ingestion_errors(self) -> None:
        from legal_doc_ingestion.exceptions import (
            CorruptedFileError,
            OCRError,
            ParsingError,
            UnsupportedFormatError,
        )

        for exc_cls in (CorruptedFileError, OCRError, ParsingError, UnsupportedFormatError):
            assert issubclass(exc_cls, IngestionError)

    def test_corrupted_file_error_attributes(self) -> None:
        exc = CorruptedFileError("/tmp/bad.pdf", reason="magic bytes invalid")
        assert exc.filepath == "/tmp/bad.pdf"
        assert "magic bytes invalid" in str(exc)
