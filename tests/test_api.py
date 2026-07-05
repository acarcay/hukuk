"""
Tests for the Legal RAG API endpoints.

Uses FastAPI TestClient with mocked services to avoid
needing a running Ollama instance or real embedding model.
"""

from __future__ import annotations

import io
import json
from typing import AsyncGenerator, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ------------------------------------------------------------------
# Mock services before importing the app
# ------------------------------------------------------------------

class MockEmbedder:
    def embed(self, text: str) -> List[float]:
        h = hash(text)
        return [(h >> i & 0xFF) / 255.0 for i in range(8)]

    def embed_batch(self, texts) -> List[List[float]]:
        return [self.embed(t) for t in texts]


class MockStore:
    def __init__(self):
        self._count = 0
        self._docs: List[Dict] = []

    @property
    def count(self) -> int:
        return self._count

    def insert_chunks(self, chunks, engine, **kwargs) -> int:
        self._count += len(chunks)
        for c in chunks:
            self._docs.append({
                "text": c.text,
                "source_id": c.source_id,
                "section_heading": c.section_heading,
            })
        return len(chunks)

    def search(self, query, engine, k=5, **kwargs):
        from legal_doc_ingestion.vectorization.store import SearchResult
        results = []
        for doc in self._docs[:k]:
            results.append(SearchResult(
                chunk_id="mock_id",
                text=doc["text"],
                distance=0.15,
                source_id=doc.get("source_id", "test.pdf"),
                section_heading=doc.get("section_heading"),
                metadata={
                    "source_id": doc.get("source_id", "test.pdf"),
                    "section_heading": doc.get("section_heading"),
                },
            ))
        return results

    def _get_collection(self):
        mock_collection = MagicMock()
        mock_collection.get.return_value = {
            "metadatas": [
                {"source_id": "test.pdf", "document_type": "pdf"}
                for _ in range(self._count)
            ]
        }
        return mock_collection


class MockLLM:
    @property
    def model(self) -> str:
        return "mock-llama3:8b"

    async def aclose(self) -> None:
        pass

    async def health_check(self) -> bool:
        return True

    async def generate_stream(self, prompt, system="", **kwargs) -> AsyncGenerator:
        tokens = ["Bu ", "sorunun ", "cevabı ", "şudur."]
        for t in tokens:
            yield t

    async def generate(self, prompt, system="", **kwargs) -> str:
        return "Bu sorunun cevabı bağlamda şu şekilde açıklanmaktadır."


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture
def mock_services():
    """Patch the global services container with mocks.

    We also patch ``services.initialize`` so that the FastAPI lifespan
    event (which calls it on TestClient startup) does NOT overwrite the
    mocks we set here with real ChromaDB / Embedder / LLM instances.
    """
    from unittest.mock import patch as _patch

    from api.dependencies import services
    from legal_doc_ingestion.ingestion import LegalDocumentIngestor
    from legal_doc_ingestion.vectorization.chunker import LegalSemanticChunker

    # Install mocks before the lifespan runs
    services.ingestor = LegalDocumentIngestor()
    services.chunker = LegalSemanticChunker(overlap_ratio=0.10, min_chunk_chars=50)
    services.embedder = MockEmbedder()
    services.store = MockStore()
    services.llm = MockLLM()

    # Patch initialize() to a no-op so TestClient lifespan cannot overwrite
    with _patch.object(services, "initialize", return_value=None):
        yield services

    # Restore to uninitialized state after test
    services.ingestor = None
    services.chunker = None
    services.embedder = None
    services.store = None
    services.llm = None


@pytest.fixture
def client(mock_services):
    """Create a TestClient with mocked services."""
    from api.main import app
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# ------------------------------------------------------------------
# Health endpoint
# ------------------------------------------------------------------

class TestHealthEndpoint:

    def test_health_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert "vector_store" in data
        assert "llm" in data

    def test_root_returns_info(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "Legal RAG API" in resp.json()["service"]


# ------------------------------------------------------------------
# Upload endpoint
# ------------------------------------------------------------------

class TestUploadEndpoint:

    def test_upload_rejects_unsupported_format(self, client):
        file_content = b"some content"
        resp = client.post(
            "/api/v1/upload",
            files=[("files", ("test.txt", io.BytesIO(file_content), "text/plain"))],
        )
        assert resp.status_code == 400
        assert "Unsupported" in resp.json()["detail"]

    def test_upload_rejects_empty_request(self, client):
        resp = client.post("/api/v1/upload")
        assert resp.status_code == 422  # validation error

    def test_upload_docx_success(self, client, mock_services, tmp_path):
        """Upload a real DOCX file and verify the pipeline runs."""
        try:
            from docx import Document as DocxDocument
        except ImportError:
            pytest.skip("python-docx not installed")

        # Create a test DOCX
        doc = DocxDocument()
        doc.add_paragraph("MADDE 1 - Taraflar")
        doc.add_paragraph("Bu sözleşme aşağıdaki taraflar arasında imzalanmıştır.")
        doc.add_paragraph("MADDE 2 - Konu")
        doc.add_paragraph("Sözleşmenin konusu burada belirtilmiştir.")

        docx_path = tmp_path / "test_contract.docx"
        doc.save(str(docx_path))
        content = docx_path.read_bytes()

        resp = client.post(
            "/api/v1/upload",
            files=[("files", ("test_contract.docx", io.BytesIO(content),
                             "application/vnd.openxmlformats-officedocument.wordprocessingml.document"))],
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_chunks"] > 0
        assert data["documents"][0]["status"] == "success"
        assert mock_services.store.count > 0


# ------------------------------------------------------------------
# Chat endpoint
# ------------------------------------------------------------------

class TestChatEndpoint:

    def _seed_store(self, mock_services):
        """Insert some chunks so the store isn't empty."""
        from legal_doc_ingestion.vectorization.chunker import TextChunk
        chunks = [
            TextChunk(
                chunk_id="c1", text="Aylık kira bedeli 15.000 TL olarak belirlenmiştir.",
                source_id="kira.pdf", section_heading="MADDE 3",
            ),
            TextChunk(
                chunk_id="c2", text="Sözleşme süresi 1 yıl olup başlangıç tarihi 01.01.2026'dır.",
                source_id="kira.pdf", section_heading="MADDE 4",
            ),
        ]
        mock_services.store.insert_chunks(chunks, mock_services.embedder)

    def test_chat_no_documents_returns_404(self, client):
        resp = client.post(
            "/api/v1/chat",
            json={"query": "Kira bedeli nedir?", "stream": False},
        )
        assert resp.status_code == 404

    def test_chat_non_streaming(self, client, mock_services):
        self._seed_store(mock_services)
        resp = client.post(
            "/api/v1/chat",
            json={"query": "Kira bedeli nedir?", "stream": False},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "answer" in data
        assert len(data["answer"]) > 0
        assert len(data["context"]) > 0
        assert data["model"] == "mock-llama3:8b"

    def test_chat_streaming_sse(self, client, mock_services):
        self._seed_store(mock_services)
        resp = client.post(
            "/api/v1/chat",
            json={"query": "Sözleşme süresi nedir?", "stream": True},
        )
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")

        content = resp.text
        assert "event: context" in content
        assert "event: token" in content
        assert "event: done" in content

    def test_chat_empty_query_rejected(self, client):
        resp = client.post(
            "/api/v1/chat",
            json={"query": "", "stream": False},
        )
        assert resp.status_code == 422

    def test_chat_with_source_filter(self, client, mock_services):
        self._seed_store(mock_services)
        resp = client.post(
            "/api/v1/chat",
            json={
                "query": "Kira bedeli?",
                "stream": False,
                "source_filter": "kira.pdf",
            },
        )
        assert resp.status_code == 200

    def test_chat_with_temperature(self, client, mock_services):
        self._seed_store(mock_services)
        resp = client.post(
            "/api/v1/chat",
            json={
                "query": "Taraflar kimdir?",
                "stream": False,
                "temperature": 0.5,
            },
        )
        assert resp.status_code == 200


# ------------------------------------------------------------------
# Documents endpoint
# ------------------------------------------------------------------

class TestDocumentsEndpoint:

    def test_documents_empty(self, client):
        resp = client.get("/api/v1/documents")
        assert resp.status_code == 200
        assert resp.json()["total_vectors"] == 0

    def test_documents_after_insert(self, client, mock_services):
        from legal_doc_ingestion.vectorization.chunker import TextChunk
        chunks = [
            TextChunk(chunk_id="d1", text="Test", source_id="a.pdf"),
            TextChunk(chunk_id="d2", text="Test", source_id="b.pdf"),
        ]
        mock_services.store.insert_chunks(chunks, mock_services.embedder)
        resp = client.get("/api/v1/documents")
        assert resp.status_code == 200
        assert resp.json()["total_vectors"] == 2
