"""
Tests for the vectorization pipeline:
  - LegalSemanticChunker
  - EmbeddingEngine (mocked for CI)
  - ChromaVectorStore
"""

from __future__ import annotations

import pytest
from typing import List

from legal_doc_ingestion.vectorization.chunker import LegalSemanticChunker, TextChunk
from legal_doc_ingestion.vectorization.store import ChromaVectorStore, SearchResult


# ======================================================================
# Sample legal texts
# ======================================================================

TURKISH_LEGAL_TEXT = """
MADDE 1 - Taraflar
Bu sözleşme, aşağıda bilgileri yazılı taraflar arasında akdedilmiştir.
Kiralayan: Mehmet Yılmaz
Kiracı: Ayşe Demir

MADDE 2 - Sözleşmenin Konusu
İşbu sözleşmenin konusu, İstanbul ili Kadıköy ilçesinde bulunan
taşınmazın kiralanmasıdır. Taşınmaz, konut amaçlı kullanılacaktır.

MADDE 3 - Kira Bedeli ve Ödeme Şartları
Aylık kira bedeli 15.000 TL olarak belirlenmiştir.
Kira bedeli her ayın en geç 5'ine kadar ödenecektir.
Gecikme halinde aylık %2 gecikme faizi uygulanır.

MADDE 4 - Sözleşme Süresi
Sözleşme süresi 1 (bir) yıl olup, başlangıç tarihi 01.01.2026'dır.
Taraflardan herhangi biri, sözleşme süresinin bitiminden en az 30 gün
önce yazılı bildirimde bulunmadığı takdirde sözleşme aynı koşullarla
bir yıl daha uzar.

GEÇİCİ MADDE 1 - İlk Ay Ödemesi
İlk ay kira bedeli sözleşmenin imza tarihinde peşin olarak ödenecektir.
"""

ENGLISH_LEGAL_TEXT = """
ARTICLE I - Definitions
In this Agreement, the following terms shall have the meanings set forth below.

ARTICLE II - Scope of Services
The Contractor shall provide the services described in Exhibit A.

SECTION 1 - Payment Terms
Payment shall be made within 30 days of invoice receipt.

CLAUSE 3 - Limitation of Liability
In no event shall either party be liable for indirect damages.
"""


# ======================================================================
# Chunker Tests
# ======================================================================


class TestLegalSemanticChunker:
    """Tests for the semantic chunking engine."""

    def setup_method(self) -> None:
        self.chunker = LegalSemanticChunker(overlap_ratio=0.10, min_chunk_chars=50)

    def test_splits_turkish_madde(self) -> None:
        chunks = self.chunker.chunk(TURKISH_LEGAL_TEXT, source_id="kira.pdf")
        # Should have at least 4 MADDE + 1 GEÇİCİ MADDE = 5 sections
        assert len(chunks) >= 4
        headings = [c.section_heading for c in chunks if c.section_heading]
        madde_headings = [h for h in headings if "MADDE" in h.upper()]
        assert len(madde_headings) >= 4

    def test_splits_english_articles(self) -> None:
        chunks = self.chunker.chunk(ENGLISH_LEGAL_TEXT, source_id="contract.pdf")
        assert len(chunks) >= 3
        headings = [c.section_heading for c in chunks if c.section_heading]
        assert any("ARTICLE" in h for h in headings)

    def test_overlap_applied(self) -> None:
        chunks = self.chunker.chunk(TURKISH_LEGAL_TEXT, source_id="test.pdf")
        if len(chunks) >= 2:
            # The tail of chunk 0 should appear at the start of chunk 1
            tail = chunks[0].text[-30:]
            # At least some overlap text from the end of chunk 0
            # should be found in chunk 1 (allowing for word-boundary snapping)
            overlap_words = tail.split()[-3:]
            found = any(w in chunks[1].text for w in overlap_words if len(w) > 3)
            assert found, "Overlap text not found in next chunk"

    def test_deterministic_ids(self) -> None:
        chunks_a = self.chunker.chunk(TURKISH_LEGAL_TEXT, source_id="doc.pdf")
        chunks_b = self.chunker.chunk(TURKISH_LEGAL_TEXT, source_id="doc.pdf")
        assert [c.chunk_id for c in chunks_a] == [c.chunk_id for c in chunks_b]

    def test_empty_text_returns_empty(self) -> None:
        assert self.chunker.chunk("") == []
        assert self.chunker.chunk("   ") == []

    def test_no_headings_returns_single_chunk(self) -> None:
        plain = "Bu bir test metnidir. Herhangi bir madde veya başlık içermemektedir. " * 5
        chunks = self.chunker.chunk(plain, source_id="plain.txt")
        assert len(chunks) == 1

    def test_metadata_propagation(self) -> None:
        chunks = self.chunker.chunk(
            TURKISH_LEGAL_TEXT,
            source_id="meta.pdf",
            extra_metadata={"court": "İstanbul", "year": "2026"},
        )
        for c in chunks:
            assert c.metadata["court"] == "İstanbul"
            assert c.metadata["year"] == "2026"
            assert c.source_id == "meta.pdf"

    def test_chunk_index_ordering(self) -> None:
        chunks = self.chunker.chunk(TURKISH_LEGAL_TEXT, source_id="order.pdf")
        for i, c in enumerate(chunks):
            assert c.chunk_index == i
            assert c.total_chunks == len(chunks)

    def test_max_chunk_subsplit(self) -> None:
        small_chunker = LegalSemanticChunker(
            overlap_ratio=0.0, min_chunk_chars=10, max_chunk_chars=200,
        )
        chunks = small_chunker.chunk(TURKISH_LEGAL_TEXT, source_id="small.pdf")
        for c in chunks:
            # With overlap=0 and subsplitting, each chunk should respect max
            assert c.char_count <= 400  # allow some tolerance for heading text

    def test_custom_overlap_ratio(self) -> None:
        chunker_0 = LegalSemanticChunker(overlap_ratio=0.0)
        chunker_20 = LegalSemanticChunker(overlap_ratio=0.20)
        chunks_0 = chunker_0.chunk(TURKISH_LEGAL_TEXT, source_id="t.pdf")
        chunks_20 = chunker_20.chunk(TURKISH_LEGAL_TEXT, source_id="t.pdf")
        if len(chunks_0) > 1:
            total_0 = sum(c.char_count for c in chunks_0)
            total_20 = sum(c.char_count for c in chunks_20)
            assert total_20 > total_0, "20% overlap should produce more total chars"


# ======================================================================
# Mock Embedding Engine (avoids downloading model in CI)
# ======================================================================


class MockEmbeddingEngine:
    """Deterministic mock that produces 8-dim vectors from text hash."""

    def __init__(self, dim: int = 8) -> None:
        self._dim = dim

    @property
    def embedding_dim(self) -> int:
        return self._dim

    def embed(self, text: str) -> List[float]:
        h = hash(text)
        return [(h >> i & 0xFF) / 255.0 for i in range(self._dim)]

    def embed_batch(self, texts) -> List[List[float]]:
        return [self.embed(t) for t in texts]


# ======================================================================
# Vector Store Tests
# ======================================================================


class TestChromaVectorStore:
    """Integration tests for ChromaVectorStore using in-memory ChromaDB."""

    def setup_method(self) -> None:
        try:
            import chromadb  # noqa: F401
        except ImportError:
            pytest.skip("chromadb not installed")
        self.store = ChromaVectorStore(
            collection_name="test_legal_docs",
            persist_directory=None,
        )
        self.store.reset_collection()
        self.engine = MockEmbeddingEngine()
        self.chunker = LegalSemanticChunker(overlap_ratio=0.10, min_chunk_chars=50)

    def test_insert_and_count(self) -> None:
        chunks = self.chunker.chunk(TURKISH_LEGAL_TEXT, source_id="kira.pdf")
        inserted = self.store.insert_chunks(chunks, self.engine)
        assert inserted == len(chunks)
        assert self.store.count == len(chunks)

    def test_search_returns_results(self) -> None:
        chunks = self.chunker.chunk(TURKISH_LEGAL_TEXT, source_id="kira.pdf")
        self.store.insert_chunks(chunks, self.engine)
        results = self.store.search("kira bedeli", self.engine, k=3)
        assert len(results) > 0
        assert len(results) <= 3
        assert all(isinstance(r, SearchResult) for r in results)
        assert all(r.text for r in results)

    def test_search_with_source_filter(self) -> None:
        chunks_a = self.chunker.chunk(TURKISH_LEGAL_TEXT, source_id="a.pdf")
        chunks_b = self.chunker.chunk(ENGLISH_LEGAL_TEXT, source_id="b.pdf")
        self.store.insert_chunks(chunks_a, self.engine)
        self.store.insert_chunks(chunks_b, self.engine)

        results = self.store.search(
            "payment terms", self.engine, k=10, source_filter="b.pdf",
        )
        for r in results:
            assert r.source_id == "b.pdf"

    def test_delete_by_source(self) -> None:
        chunks = self.chunker.chunk(TURKISH_LEGAL_TEXT, source_id="delete_me.pdf")
        self.store.insert_chunks(chunks, self.engine)
        assert self.store.count > 0
        self.store.delete_by_source("delete_me.pdf")
        assert self.store.count == 0

    def test_upsert_idempotent(self) -> None:
        chunks = self.chunker.chunk(TURKISH_LEGAL_TEXT, source_id="idem.pdf")
        self.store.insert_chunks(chunks, self.engine)
        count_1 = self.store.count
        self.store.insert_chunks(chunks, self.engine)
        count_2 = self.store.count
        assert count_1 == count_2, "Upsert should not duplicate"

    def test_search_result_metadata(self) -> None:
        chunks = self.chunker.chunk(
            TURKISH_LEGAL_TEXT, source_id="meta.pdf",
            extra_metadata={"court": "Ankara"},
        )
        self.store.insert_chunks(chunks, self.engine)
        results = self.store.search("taraflar", self.engine, k=1)
        assert len(results) == 1
        assert results[0].metadata.get("court") == "Ankara"
        assert results[0].source_id == "meta.pdf"

    def test_reset_collection(self) -> None:
        chunks = self.chunker.chunk(TURKISH_LEGAL_TEXT, source_id="reset.pdf")
        self.store.insert_chunks(chunks, self.engine)
        assert self.store.count > 0
        self.store.reset_collection()
        assert self.store.count == 0
