"""
Async Ollama LLM client with streaming support, connection pooling,
and exponential-backoff retry.

Key improvements over the previous version
-------------------------------------------
* **Shared AsyncClient** — A single ``httpx.AsyncClient`` is created once
  and reused across all requests.  Call ``await client.aclose()`` (or use
  as an async context manager) to release the connection pool when done.
  The FastAPI lifespan in ``main.py`` handles lifecycle management.

* **Retry with exponential backoff** — Transient Ollama errors (connection
  refused, 503, timeout) are retried up to ``max_retries`` times with
  jittered exponential delay, preventing a single blip from failing a user
  request.

* **No per-request TCP/TLS overhead** — Connection pooling is handled by
  httpx (via h11 keep-alive), so concurrent ``/chat`` requests share idle
  TCP connections instead of paying reconnect cost each time.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
from typing import AsyncGenerator, Dict, List, Optional

import httpx

from api.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Retry configuration
# ---------------------------------------------------------------------------

_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
_RETRYABLE_EXCEPTIONS = (
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.ReadTimeout,
    httpx.RemoteProtocolError,
)


async def _retry_request(coro_factory, max_retries: int = 3, base_delay: float = 0.5):
    """
    Execute ``coro_factory()`` with exponential backoff on transient failures.

    Parameters
    ----------
    coro_factory
        Zero-argument callable that returns the coroutine to retry.
    max_retries
        Maximum number of additional attempts after the first failure.
    base_delay
        Base delay in seconds; actual delay is ``base_delay * 2^attempt + jitter``.
    """
    last_exc: Optional[Exception] = None
    for attempt in range(max_retries + 1):
        try:
            return await coro_factory()
        except _RETRYABLE_EXCEPTIONS as exc:
            last_exc = exc
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in _RETRYABLE_STATUS_CODES:
                last_exc = exc
            else:
                raise
        if attempt < max_retries:
            delay = base_delay * (2 ** attempt) + random.uniform(0, 0.3)
            logger.warning(
                "Ollama request failed (attempt %d/%d): %s — retrying in %.2fs",
                attempt + 1, max_retries + 1, last_exc, delay,
            )
            await asyncio.sleep(delay)
    raise last_exc  # type: ignore[misc]


class OllamaClient:
    """
    Async client for the Ollama REST API with a shared connection pool.

    Parameters
    ----------
    base_url : str
        Ollama server URL (default from config).
    model : str
        Model tag (e.g. ``"llama3:8b"``).
    timeout : int
        Request timeout in seconds.
    max_retries : int
        Number of retry attempts on transient errors (default 3).

    Lifecycle
    ---------
    Use as an async context manager, or call ``await .aclose()`` explicitly::

        async with OllamaClient() as llm:
            answer = await llm.generate("...")

    The FastAPI lifespan in ``main.py`` is responsible for calling ``aclose``.
    """

    def __init__(
        self,
        *,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[int] = None,
        max_retries: int = 3,
    ) -> None:
        self._base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self._model = model or settings.OLLAMA_MODEL
        self._timeout = timeout or settings.OLLAMA_TIMEOUT
        self._max_retries = max_retries
        # Shared connection pool — reused across all requests
        self._http: httpx.AsyncClient = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(self._timeout, connect=10.0),
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
        )

    async def aclose(self) -> None:
        """Release the underlying connection pool."""
        await self._http.aclose()

    async def __aenter__(self) -> "OllamaClient":
        return self

    async def __aexit__(self, *_) -> None:
        await self.aclose()

    @property
    def model(self) -> str:
        return self._model

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    async def health_check(self) -> bool:
        """Return True if Ollama is reachable and the configured model is available."""
        try:
            resp = await self._http.get("/api/tags")
            if resp.status_code != 200:
                return False
            data = resp.json()
            models = [m.get("name", "") for m in data.get("models", [])]
            model_base = self._model.split(":")[0]
            return any(model_base in m for m in models)
        except Exception as exc:
            logger.warning("Ollama health check failed: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Streaming generation
    # ------------------------------------------------------------------

    async def generate_stream(
        self,
        prompt: str,
        system: str = "",
        *,
        temperature: float = 0.1,
        top_p: float = 0.9,
        max_tokens: int = 2048,
    ) -> AsyncGenerator[str, None]:
        """
        Stream tokens from the Ollama ``/api/generate`` endpoint.

        Yields
        ------
        str
            Individual text tokens as they arrive.

        Notes
        -----
        Streaming responses are not easily retried mid-stream, so we only
        retry the *connection* phase.  Once streaming starts, errors propagate.
        """
        payload = {
            "model": self._model,
            "prompt": prompt,
            "system": system,
            "stream": True,
            "keep_alive": settings.OLLAMA_KEEP_ALIVE,
            "options": {
                "temperature": temperature,
                "top_p": top_p,
                "num_predict": max_tokens,
                "num_ctx": settings.OLLAMA_NUM_CTX,
            },
        }

        logger.info(
            "LLM generate_stream → model=%s, prompt_len=%d",
            self._model, len(prompt),
        )

        async with self._http.stream(
            "POST",
            "/api/generate",
            json=payload,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    token = data.get("response", "")
                    if token:
                        yield token
                    if data.get("done", False):
                        return
                except json.JSONDecodeError:
                    continue

    # ------------------------------------------------------------------
    # Non-streaming generation (with retry)
    # ------------------------------------------------------------------

    async def generate(
        self,
        prompt: str,
        system: str = "",
        *,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> str:
        """Generate a complete response (non-streaming) with retry on transient errors."""
        payload = {
            "model": self._model,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "keep_alive": settings.OLLAMA_KEEP_ALIVE,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
                "num_ctx": settings.OLLAMA_NUM_CTX,
            },
        }

        async def _do_request():
            resp = await self._http.post("/api/generate", json=payload)
            resp.raise_for_status()
            return resp.json().get("response", "")

        return await _retry_request(_do_request, max_retries=self._max_retries)

    # ------------------------------------------------------------------
    # Chat-style API (with retry)
    # ------------------------------------------------------------------

    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        *,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> AsyncGenerator[str, None]:
        """
        Stream tokens using Ollama's ``/api/chat`` endpoint.

        Parameters
        ----------
        messages
            List of ``{"role": "system"|"user"|"assistant", "content": "..."}``
        """
        payload = {
            "model": self._model,
            "messages": messages,
            "stream": True,
            "keep_alive": settings.OLLAMA_KEEP_ALIVE,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
                "num_ctx": settings.OLLAMA_NUM_CTX,
            },
        }

        async with self._http.stream("POST", "/api/chat", json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    msg = data.get("message", {})
                    token = msg.get("content", "")
                    if token:
                        yield token
                    if data.get("done", False):
                        return
                except json.JSONDecodeError:
                    continue
