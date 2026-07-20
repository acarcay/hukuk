# Legal RAG System — Hukuk

A production-grade **Retrieval-Augmented Generation** system for Turkish and English legal documents. Full pipeline: document parsing → OCR → text cleaning → semantic chunking → multilingual embedding → ChromaDB storage → **streaming LLM answers** via a FastAPI REST API.

## Features

### Ingestion Pipeline
- **Multi-format parsing** — PDF (PyMuPDF/fitz), DOCX (python-docx), RTF (striprtf)
- **OCR fallback** — Automatic pytesseract OCR for scanned/image-heavy PDF pages
- **Text cleaning pipeline** — Removes watermarks, page numbers, header/footer noise
- **Structured JSON output** — Pydantic v2 models with metadata

### Vectorization Pipeline
- **Semantic chunking** — Splits by legal structure (Article/Madde, Section/Bölüm, Clause/Fıkra)
- **Multilingual embeddings** — `paraphrase-multilingual-MiniLM-L12-v2` (384-dim, 50+ languages)
- **ChromaDB vector store** — Persistent storage with k-NN similarity search

### RAG API *(NEW)*
- **FastAPI REST API** — Async, concurrent request handling
- **`/upload`** — Upload documents, triggers full ingestion→embedding pipeline
- **`/chat`** — Query with streaming SSE or JSON response
- **Local LLM** — Ollama integration (Llama-3-8B or any quantized model)
- **Zero-Hallucination** — Strict context-only answering policy
- **CORS + Logging** — Production-ready middleware

## Project Structure

```
hukuk/
├── requirements.txt
├── legal_doc_ingestion/           # Core library
│   ├── models.py                  # Pydantic data models
│   ├── cleaning.py                # Text cleaning pipeline
│   ├── ingestion.py               # Ingestion orchestrator
│   ├── parsers/                   # Format-specific parsers
│   │   ├── pdf_parser.py          # PyMuPDF + OCR
│   │   ├── docx_parser.py         # python-docx
│   │   └── rtf_parser.py          # striprtf
│   └── vectorization/             # Chunking + embedding
│       ├── chunker.py             # Legal semantic chunker
│       ├── embedder.py            # sentence-transformers engine
│       └── store.py               # ChromaDB vector store
├── api/                           # FastAPI application (NEW)
│   ├── main.py                    # App entry point + middleware
│   ├── config.py                  # Environment-based settings
│   ├── dependencies.py            # Service container (DI)
│   ├── llm.py                     # Async Ollama client
│   ├── prompts.py                 # Zero-hallucination templates
│   └── routes/
│       ├── upload.py              # POST /upload
│       └── chat.py                # POST /chat + GET /documents
└── tests/
    ├── test_ingestion.py
    ├── test_vectorization.py
    └── test_api.py                # API endpoint tests
```

## Installation

```bash
pip install -r requirements.txt

# For OCR support (optional):
brew install tesseract tesseract-lang   # macOS
```

## Quick Start — Ingestion

```python
from legal_doc_ingestion import LegalDocumentIngestor

ingestor = LegalDocumentIngestor()
result = ingestor.ingest("sozlesme.pdf")
print(result.to_json())
```

## Quick Start — Vectorization (End-to-End)

```python
from legal_doc_ingestion import (
    LegalDocumentIngestor,
    LegalSemanticChunker,
    EmbeddingEngine,
    ChromaVectorStore,
)

# 1. Ingest & clean the document
ingestor = LegalDocumentIngestor()
result = ingestor.ingest("kira_sozlesmesi.pdf")
cleaned_text = result.full_cleaned_text()

# 2. Chunk by legal structure (Article/Madde boundaries)
chunker = LegalSemanticChunker(overlap_ratio=0.10)
chunks = chunker.chunk(cleaned_text, source_id="kira_sozlesmesi.pdf")

print(f"Created {len(chunks)} semantic chunks")
for c in chunks[:3]:
    print(f"  [{c.section_heading}] {c.char_count} chars")

# 3. Generate embeddings & store in ChromaDB
engine = EmbeddingEngine()                        # multilingual MiniLM
store = ChromaVectorStore(persist_directory="./chroma_db")

store.insert_chunks(chunks, engine)               # multithreaded embedding
print(f"Stored {store.count} vectors")

# 4. Semantic search
results = store.search("kira bedeli artış oranı", engine, k=5)
for r in results:
    print(f"[{r.distance:.4f}] {r.section_heading}: {r.text[:100]}…")
```

## Semantic Chunking Details

The `LegalSemanticChunker` recognizes these legal structural patterns:

| Pattern | Examples |
|---------|----------|
| **MADDE / Article** | `MADDE 1 - Taraflar`, `ARTICLE IV - Definitions` |
| **BÖLÜM / Section** | `BÖLÜM 2 - Genel Hükümler`, `SECTION 3 - Payment` |
| **FIKRA / Clause** | `Fıkra 1`, `CLAUSE 3 - Liability` |
| **KISIM / Part** | `KISIM I`, `PART II - Obligations` |
| **FASIL / Chapter** | `Fasıl III`, `CHAPTER 1` |
| **GEÇİCİ MADDE** | `GEÇİCİ MADDE 1 - İlk Ay Ödemesi` |

### Configuration

```python
chunker = LegalSemanticChunker(
    overlap_ratio=0.10,      # 10% overlap between adjacent chunks
    min_chunk_chars=100,      # merge sections smaller than this
    max_chunk_chars=3000,     # sub-split oversized sections at sentence boundaries
)
```

## Embedding Engine

```python
engine = EmbeddingEngine(
    model_name="paraphrase-multilingual-MiniLM-L12-v2",
    device="cpu",             # or "cuda", "mps"
    batch_size=64,            # texts per encoding call
    max_workers=4,            # threads for parallel encoding
    normalize=True,           # L2-normalize to unit vectors
)

# Single text
vec = engine.embed("Kira sözleşmesinin feshi")

# Batch (multithreaded)
vecs = engine.embed_batch(["text 1", "text 2", "text 3"])
```

## ChromaDB Vector Store

```python
# Persistent storage
store = ChromaVectorStore(
    collection_name="legal_documents",
    persist_directory="./chroma_db",
    distance_metric="cosine",         # or "l2", "ip"
)

# Insert chunks
store.insert_chunks(chunks, engine)

# Search with metadata filter
results = store.search(
    "tahliye şartları",
    engine,
    k=5,
    source_filter="kira_sozlesmesi.pdf",
)

# Delete by source document
store.delete_by_source("old_contract.pdf")

# Reset entire collection
store.reset_collection()
```

## RAG API

### Prerequisites

```bash
# 1. Install Ollama (https://ollama.ai)
brew install ollama       # macOS

# 2. Pull a quantized model
ollama pull llama3:8b

# 3. Start Ollama server
ollama serve
```

### Start the API

```bash
pip install -r requirements.txt

# Development
PYTHONPATH=. uvicorn api.main:app --reload --port 8000

# Production (single worker — see note below)
API_KEY=your-strong-secret \
PYTHONPATH=. uvicorn api.main:app --host 0.0.0.0 --port 8000
```

> **⚠ Do not use `--workers N` with the default local ChromaDB.**
> Each worker is a separate process that opens the same persistent SQLite
> store (risking lock contention/corruption) and loads its own copy of the
> embedding model (~0.5 GB each). For horizontal scaling, run ChromaDB in
> client/server mode and point `CHROMA_*` at it, then scale workers.

### Authentication

Set the `API_KEY` environment variable (or put it in `.env`) to require an
`X-API-Key` header on `/upload`, `/chat`, and `/documents`. When `API_KEY`
is unset, auth is **disabled** — intended for local development only; the
server logs a warning at startup. `/health` and `/` stay public.

```bash
curl -H "X-API-Key: your-strong-secret" http://localhost:8000/api/v1/documents
```

Configuration can be supplied via environment variables **or** a `.env`
file in the project root (see `.env.example`).

Open **http://localhost:8000/docs** for interactive Swagger documentation.

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/upload` | Upload PDF/DOCX/RTF → ingest → chunk → embed → store |
| `POST` | `/api/v1/chat` | Query with RAG → streaming SSE or JSON response |
| `GET` | `/api/v1/documents` | List all indexed documents |
| `GET` | `/health` | System health check |

### Upload a Document

```bash
curl -X POST http://localhost:8000/api/v1/upload \
  -F "files=@sozlesme.pdf"
```

### Chat (Non-Streaming)

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "Kira bedeli nedir?", "stream": false}'
```

### Chat (Streaming SSE)

```bash
curl -N -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "Kira bedeli nedir?", "stream": true}'
```

SSE events: `context` → `token`* → `done`

### Environment Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `API_HOST` | `127.0.0.1` | Bind address (use `0.0.0.0` to expose) |
| `API_KEY` | *(empty)* | If set, requires `X-API-Key` header on sensitive endpoints |
| `OLLAMA_MODEL` | `llama3.1:8b` | Ollama model tag |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_KEEP_ALIVE` | `30m` | Keep model resident to avoid cold-load latency (`-1` = never unload) |
| `OLLAMA_NUM_CTX` | `4096` | Context window (tokens); must fit system prompt + RAG context or Ollama silently truncates |
| `EMBEDDING_MODEL` | `paraphrase-multilingual-MiniLM-L12-v2` | Sentence-transformer model |
| `CHROMA_PERSIST_DIR` | `./chroma_db` | ChromaDB storage path |
| `RAG_TOP_K` | `5` | Context chunks to retrieve (fewer = faster generation) |
| `CORS_ORIGINS` | `http://localhost:3000,8080,...` | Allowed CORS origins (`*` disables credentials) |
| `AUDIT_LOG_FILE` | `logs/access.log` | KVKK access-audit trail file (`""` to disable) |

## Error Handling

```python
from legal_doc_ingestion.exceptions import (
    IngestionError, CorruptedFileError,
    UnsupportedFormatError, OCRError, ParsingError,
)

try:
    result = ingestor.ingest("damaged.pdf")
except CorruptedFileError as e:
    print(f"File corrupted: {e}")
except IngestionError as e:
    print(f"General error: {e}")
```

## Running Tests

```bash
pip install pytest
PYTHONPATH=. pytest tests/ -v
```

## License

Internal / Proprietary
