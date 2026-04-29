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
from typing import Dict, List, Optional

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
    source_filter: Optional[str] = Field(
        None, description="Filter results to a specific document (source_id)"
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

def _retrieve_context(
    query: str,
    top_k: int,
    source_filter: Optional[str],
) -> List[Dict]:
    """
    Synchronous context retrieval from ChromaDB.
    Runs in executor to avoid blocking the event loop.
    """
    results = services.store.search(
        query,
        services.embedder,
        k=top_k,
        source_filter=source_filter,
    )

    # Truncate total context to stay within token budget
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
        })
        total_chars += len(r.text)

    return context_chunks


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
            }
            for c in context_chunks
        ]
    }
    yield f"event: context\ndata: {json.dumps(context_event, ensure_ascii=False)}\n\n"

    # Build prompt
    user_prompt = build_rag_prompt(query, context_chunks, language_hint=language)

    # Stream LLM tokens
    gen_start = time.monotonic()
    token_count = 0

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
    temperature = request.temperature if request.temperature is not None else 0.1

    # Check vector store has documents
    if services.store.count == 0:
        raise HTTPException(
            status_code=404,
            detail="No documents have been uploaded yet. "
                   "Use POST /upload to add documents first.",
        )

    # Retrieve context (CPU-bound, run in thread)
    loop = asyncio.get_event_loop()
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
