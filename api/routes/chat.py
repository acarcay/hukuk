"""
POST /chat — Receive a user query, retrieve relevant context from
ChromaDB, format a zero-hallucination prompt, and stream the LLM
response back via Server-Sent Events (SSE).
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional, Union

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from api.config import settings
from api.dependencies import services
from api.prompts import SYSTEM_PROMPT, build_rag_prompt

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Chat"])


# ------------------------------------------------------------------
# Request / Response schemas
# ------------------------------------------------------------------

class ChatRequest(BaseModel):
    """Incoming chat request."""

    query: str = Field(..., min_length=1, max_length=2000, description="User question")
    source_filter: Optional[Union[str, List[str]]] = Field(
        None, description="Filter results to specific document(s) (source_id)"
    )
    top_k: Optional[int] = Field(
        None, ge=1, le=20, description="Number of context chunks to retrieve"
    )
    temperature: Optional[float] = Field(
        None, ge=0.0, le=2.0, description="LLM sampling temperature"
    )
    stream: bool = Field(True, description="Stream the response via SSE")
    language: Optional[str] = Field(
        None, description="Preferred response language (e.g. 'Turkish', 'English')"
    )


class ContextChunk(BaseModel):
    """A retrieved context chunk included in the response."""

    source_id: str
    section_heading: Optional[str]
    text: str
    distance: float
    page_number: int = 1


class ChatResponse(BaseModel):
    """Non-streaming chat response."""

    answer: str
    context: List[ContextChunk]
    model: str
    retrieval_time_ms: float
    generation_time_ms: float


# ------------------------------------------------------------------
# Context retrieval (runs in thread pool)
# ------------------------------------------------------------------

import re as _re


def _detect_article_range(query: str):
    """
    Detect if the query asks for a range of articles by number.
    Returns (start, end) tuple or None.
    Examples: "ilk 10 madde" → (1, 10), "madde 1-5" → (1, 5)
    """
    q = query.lower()

    # "ilk N madde", "ilk on madde vb."
    m = _re.search(r'ilk\s+(\d+)\s*madde', q)
    if m:
        return 1, int(m.group(1))

    # "madde 1'den 10'a", "1. maddeden 10. maddeye"
    m = _re.search(r'madde\s*(\d+)[^\d]+?(\d+)', q)
    if m:
        return int(m.group(1)), int(m.group(2))

    # "madde 1-10", "1-10. maddeler"
    m = _re.search(r'(\d+)\s*[-–]\s*(\d+)\.?\s*madde', q)
    if m:
        return int(m.group(1)), int(m.group(2))

    return None


def _retrieve_by_article_range(
    start: int,
    end: int,
    source_filter,
    top_k: int,
    query: str = "",
) -> List[Dict]:
    """
    Retrieve chunks whose section_heading contains MADDE/Article numbers
    in the given range directly from ChromaDB (no embedding needed).
    """
    collection = services.store._get_collection()

    # Build heading patterns for each article number in range
    article_nums = list(range(start, end + 1))
    # ChromaDB $in filter on section_heading won't work since heading is a rich string.
    # Instead fetch all docs and filter in Python.
    where: Dict = {}
    if source_filter:
        if isinstance(source_filter, list) and len(source_filter) == 1:
            where = {"source_id": source_filter[0]}
        elif isinstance(source_filter, list):
            where = {"source_id": {"$in": source_filter}}
        elif isinstance(source_filter, str):
            where = {"source_id": source_filter}

    kwargs = {
        "include": ["documents", "metadatas"],
        "limit": min(collection.count(), 2000),
    }
    if where:
        kwargs["where"] = where

    raw = collection.get(**kwargs)

    chunks: List[Dict] = []
    if not raw["ids"]:
        return chunks

    # Match section headings containing the exact article numbers
    for i, doc_id in enumerate(raw["ids"]):
        meta = raw["metadatas"][i] if raw["metadatas"] else {}
        heading = meta.get("section_heading", "") or ""
        text = raw["documents"][i] if raw["documents"] else ""

        # Check if heading contains one of the target article numbers
        # Match "MADDE 1", "Madde 10 -" but NOT "GEÇİCİ MADDE 1"
        heading_match = _re.search(
            r'(?<!\w)(?:MADDE|Madde|ARTICLE|Article)\s+(\d+)(?!\s*\w*MADDE)',
            heading
        )
        if heading_match:
            num = int(heading_match.group(1))
            if num in article_nums:
                # Avoid GEÇİCİ MADDE — check heading doesn't start with a qualifier
                if not _re.search(r'GEÇİCİ|GECİCİ|TEMPORARY|PROVISIONAL', heading.upper()):
                    chunks.append({
                        "text": text,
                        "source_id": meta.get("source_id", ""),
                        "section_heading": heading,
                        "distance": 0.0,
                        "page_number": meta.get("page_number", 1),
                    })

    # Deduplicate: if multiple chunks share the same article number, keep the best one.
    # "Best" = chunk whose text has most overlap with the original query terms.
    query_terms = set(_re.findall(r'\w+', query.lower()))

    by_num: Dict[int, List[Dict]] = {}
    for chunk in chunks:
        m = _re.search(r'\d+', chunk["section_heading"] or "")
        if m:
            num = int(m.group())
            by_num.setdefault(num, []).append(chunk)

    deduped: List[Dict] = []
    for num in sorted(by_num):
        candidates = by_num[num]
        if len(candidates) == 1:
            deduped.append(candidates[0])
        else:
            # Score by term overlap with query
            def score(c):
                text_terms = set(_re.findall(r'\w+', c["text"].lower()))
                return len(query_terms & text_terms)
            best = max(candidates, key=score)
            deduped.append(best)

    return deduped[:top_k]


def _retrieve_context(
    query: str,
    top_k: int,
    source_filter: Optional[Union[str, List[str]]],
) -> List[Dict]:
    """
    Synchronous context retrieval from ChromaDB.
    Uses article-range detection for ordinal queries,
    falls back to semantic search for general queries.
    Runs in executor to avoid blocking the event loop.
    """
    # --- Strategy 1: Article-range query (e.g. "ilk 10 madde") ---
    article_range = _detect_article_range(query)
    if article_range:
        start, end = article_range
        # Cap range to avoid absurd requests
        end = min(end, start + 49)
        range_chunks = _retrieve_by_article_range(
            start, end, source_filter, top_k=end - start + 1, query=query
        )
        if range_chunks:
            # Mark chunks as coming from article-range retrieval
            for c in range_chunks:
                c["_article_range"] = True
            return range_chunks

    # --- Strategy 2: Standard semantic search ---
    results = services.store.search(
        query,
        services.embedder,
        k=top_k,
        source_filter=source_filter,
    )

    context_chunks: List[Dict] = []
    total_chars = 0

    for r in results:
        if total_chars + len(r.text) > settings.RAG_MAX_CONTEXT_CHARS:
            break
        context_chunks.append({
            "text": r.text,
            "source_id": r.source_id,
            "section_heading": r.section_heading,
            "distance": r.distance,
            "page_number": r.page_number,
        })
        total_chars += len(r.text)

    return context_chunks


# ------------------------------------------------------------------
# Direct article formatter (bypasses LLM for article-range queries)
# ------------------------------------------------------------------

def _format_article_range_answer(context_chunks: List[Dict]) -> str:
    """
    Format retrieved article chunks as a numbered list directly,
    without calling the LLM. Guaranteed accurate since it's just
    copying the indexed text verbatim.
    """
    lines = []
    for c in context_chunks:
        heading = c.get("section_heading") or ""
        text = c.get("text", "").strip()
        if heading:
            lines.append(f"**{heading}**")
        if text:
            # Clean up OCR artifacts (excessive newlines)
            clean = _re.sub(r'\n{3,}', '\n\n', text).strip()
            lines.append(clean)
        lines.append("")
    return "\n".join(lines).strip()


# ------------------------------------------------------------------
# SSE streaming
# ------------------------------------------------------------------

async def _stream_sse(
    query: str,
    context_chunks: List[Dict],
    temperature: float,
    language: Optional[str],
    retrieval_time_ms: float,
):
    """
    Async generator that yields Server-Sent Events.

    Event types:
      - ``context``  : The retrieved context chunks (sent once at the start)
      - ``token``    : Individual LLM tokens
      - ``done``     : Final event with timing metadata
      - ``error``    : Error information
    """
    # Send context first
    context_event = {
        "chunks": [
            {
                "source_id": c["source_id"],
                "section_heading": c.get("section_heading"),
                "text": c["text"][:200] + "…" if len(c["text"]) > 200 else c["text"],
                "distance": round(c["distance"], 4),
                "page_number": c.get("page_number", 1),
            }
            for c in context_chunks
        ]
    }
    yield f"event: context\ndata: {json.dumps(context_event, ensure_ascii=False)}\n\n"

    # --- Article-range: bypass LLM, stream the formatted answer directly ---
    is_article_range = any(c.get("_article_range") for c in context_chunks)
    if is_article_range:
        gen_start = time.monotonic()
        answer_text = _format_article_range_answer(context_chunks)
        # Stream word by word to keep the SSE token flow working
        for word in answer_text.split(" "):
            yield f"event: token\ndata: {json.dumps({'token': word + ' '}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0)  # yield control
        gen_time_ms = (time.monotonic() - gen_start) * 1000
        done_data = {
            "model": "direct-extraction",
            "tokens_generated": len(answer_text.split()),
            "retrieval_time_ms": round(retrieval_time_ms, 2),
            "generation_time_ms": round(gen_time_ms, 2),
        }
        yield f"event: done\ndata: {json.dumps(done_data)}\n\n"
        return


    # Stream LLM tokens
    gen_start = time.monotonic()
    token_count = 0

    user_prompt = build_rag_prompt(
        query, context_chunks, language_hint=language
    )

    try:
        async for token in services.llm.generate_stream(
            prompt=user_prompt,
            system=SYSTEM_PROMPT,
            temperature=temperature,
        ):
            token_count += 1
            yield f"event: token\ndata: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"

        gen_time_ms = (time.monotonic() - gen_start) * 1000

        done_data = {
            "model": services.llm.model,
            "tokens_generated": token_count,
            "retrieval_time_ms": round(retrieval_time_ms, 2),
            "generation_time_ms": round(gen_time_ms, 2),
        }
        yield f"event: done\ndata: {json.dumps(done_data)}\n\n"

    except Exception as exc:
        logger.exception("LLM streaming error")
        error_data = {"error": str(exc), "type": type(exc).__name__}
        yield f"event: error\ndata: {json.dumps(error_data)}\n\n"


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------

@router.post(
    "/chat",
    summary="Ask a question about uploaded legal documents",
    description=(
        "Retrieves relevant context from the vector store and generates "
        "an answer using the local LLM. Supports streaming (SSE) and "
        "non-streaming modes. Enforces a Zero-Hallucination policy."
    ),
)
async def chat(request: ChatRequest):
    """Handle a RAG chat request."""
    top_k = request.top_k or settings.RAG_TOP_K
    temperature = request.temperature if request.temperature is not None else 0.0

    # Check vector store has documents
    if services.store.count == 0:
        raise HTTPException(
            status_code=404,
            detail="No documents have been uploaded yet. "
                   "Use POST /upload to add documents first.",
        )

    # Retrieve context (CPU-bound, run in thread)
    loop = asyncio.get_running_loop()
    t0 = time.monotonic()

    context_chunks = await loop.run_in_executor(
        None, _retrieve_context, request.query, top_k, request.source_filter
    )

    retrieval_ms = (time.monotonic() - t0) * 1000

    if not context_chunks:
        raise HTTPException(
            status_code=404,
            detail="No relevant context found for your query. "
                   "Try rephrasing or uploading more documents.",
        )

    logger.info(
        "Retrieved %d context chunks (%.1f ms) for query: %.80s…",
        len(context_chunks), retrieval_ms, request.query,
    )

    # ------------------------------------------------------------------
    # Streaming response
    # ------------------------------------------------------------------
    if request.stream:
        return StreamingResponse(
            _stream_sse(
                query=request.query,
                context_chunks=context_chunks,
                temperature=temperature,
                language=request.language,
                retrieval_time_ms=retrieval_ms,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # ------------------------------------------------------------------
    # Non-streaming response
    # ------------------------------------------------------------------

    # Article-range: bypass LLM entirely, format answer directly
    is_article_range = any(c.get("_article_range") for c in context_chunks)
    if is_article_range:
        answer = _format_article_range_answer(context_chunks)
        gen_ms = 0.0
    else:
        user_prompt = build_rag_prompt(
            request.query, context_chunks, language_hint=request.language
        )
        t1 = time.monotonic()
        answer = await services.llm.generate(
            prompt=user_prompt,
            system=SYSTEM_PROMPT,
            temperature=temperature,
        )
        gen_ms = (time.monotonic() - t1) * 1000

    return ChatResponse(
        answer=answer,
        context=[
            ContextChunk(
                source_id=c["source_id"],
                section_heading=c.get("section_heading"),
                text=c["text"],
                distance=c["distance"],
                page_number=c.get("page_number", 1),
            )
            for c in context_chunks
        ],
        model=services.llm.model,
        retrieval_time_ms=round(retrieval_ms, 2),
        generation_time_ms=round(gen_ms, 2),
    )


# ------------------------------------------------------------------
# Utility endpoints
# ------------------------------------------------------------------

@router.get(
    "/documents",
    summary="List all indexed document sources",
    tags=["Documents"],
)
async def list_documents():
    """Return metadata about documents currently in the vector store."""
    collection = services.store._get_collection()
    all_data = collection.get(include=["metadatas"])

    sources: Dict[str, Dict] = {}
    if all_data["metadatas"]:
        for meta in all_data["metadatas"]:
            sid = meta.get("source_id", "unknown")
            if sid not in sources:
                sources[sid] = {
                    "source_id": sid,
                    "document_type": meta.get("document_type", "unknown"),
                    "chunk_count": 0,
                }
            sources[sid]["chunk_count"] += 1

    return {
        "total_vectors": services.store.count,
        "documents": list(sources.values()),
    }
@router.delete(
    "/documents/{source_id}",
    summary="Delete a document and its vectors",
    tags=["Documents"],
)
async def delete_document(source_id: str):
    """Remove a document from the vector store and delete its source file."""
    # 1. Retrieve disk_filename from ChromaDB *before* deleting vectors
    disk_filename: Optional[str] = None
    try:
        collection = services.store._get_collection()
        raw = collection.get(
            where={"source_id": source_id},
            include=["metadatas"],
            limit=1,
        )
        if raw["metadatas"]:
            disk_filename = raw["metadatas"][0].get("disk_filename")
    except Exception as exc:
        logger.warning("Could not read disk_filename for %s: %s", source_id, exc)

    # 2. Delete vectors from ChromaDB
    try:
        services.store.delete_by_source(source_id)
    except Exception as exc:
        logger.error("Failed to delete vectors for %s: %s", source_id, exc)

    # 3. Delete physical file using the stored disk_filename
    if disk_filename:
        file_path = Path(settings.UPLOAD_DIR) / disk_filename
    else:
        # Fallback for documents uploaded before this fix
        file_path = Path(settings.UPLOAD_DIR) / source_id

    if file_path.exists():
        try:
            file_path.unlink()
            logger.info("Deleted file: %s", file_path)
        except OSError as exc:
            logger.error("Failed to delete file %s: %s", file_path, exc)
    else:
        logger.warning("Physical file not found on disk: %s", file_path)

    return {"status": "success", "message": f"Document {source_id} deleted."}
