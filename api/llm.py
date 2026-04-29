"""
Async Ollama LLM client with streaming support.

Communicates with a local Ollama instance via its HTTP API
to run quantized LLMs (e.g. Llama-3-8B-Q4) for generation.
"""

from __future__ import annotations

import json
import logging
from typing import AsyncGenerator, Dict, List, Optional

import httpx

from api.config import settings

logger = logging.getLogger(__name__)


class OllamaClient:
    """
    Async client for the Ollama REST API.

    Parameters
    ----------
    base_url : str
        Ollama server URL (default from config).
    model : str
        Model tag (e.g. ``"llama3:8b"``).
    timeout : int
        Request timeout in seconds.
    """

    def __init__(
        self,
        *,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> None:
        self._base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self._model = model or settings.OLLAMA_MODEL
        self._timeout = timeout or settings.OLLAMA_TIMEOUT

    @property
    def model(self) -> str:
        return self._model

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    async def health_check(self) -> bool:
        """Return True if Ollama is reachable and the model is available."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{self._base_url}/api/tags")
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
        """
        payload = {
            "model": self._model,
            "prompt": prompt,
            "system": system,
            "stream": True,
            "options": {
                "temperature": temperature,
                "top_p": top_p,
                "num_predict": max_tokens,
            },
        }

        logger.info(
            "LLM generate_stream → model=%s, prompt_len=%d",
            self._model, len(prompt),
        )

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            async with client.stream(
                "POST",
                f"{self._base_url}/api/generate",
                json=payload,
                timeout=self._timeout,
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
    # Non-streaming generation
    # ------------------------------------------------------------------

    async def generate(
        self,
        prompt: str,
        system: str = "",
        *,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> str:
        """Generate a complete response (non-streaming)."""
        payload = {
            "model": self._model,
            "prompt": prompt,
            "system": system,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                f"{self._base_url}/api/generate",
                json=payload,
                timeout=self._timeout,
            )
            resp.raise_for_status()
            return resp.json().get("response", "")

    # ------------------------------------------------------------------
    # Chat-style API
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
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            async with client.stream(
                "POST",
                f"{self._base_url}/api/chat",
                json=payload,
                timeout=self._timeout,
            ) as response:
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
