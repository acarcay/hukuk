"""
Embedding generation engine using a lightweight, multilingual
sentence-transformer model suitable for local execution.

Default model: ``paraphrase-multilingual-MiniLM-L12-v2``
  - 118M params, ~470 MB, 50+ languages (incl. Turkish)
  - 384-dimensional embeddings, fast CPU inference

``embed_batch`` delegates entirely to ``model.encode()`` which already
uses optimised BLAS/OMP thread pools internally.  Wrapping it in an
additional ``ThreadPoolExecutor`` causes CPU oversubscription and can
actually *reduce* throughput — so we use a single vectorised call instead.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
_DEFAULT_BATCH_SIZE = 64


class EmbeddingEngine:
    """
    Generates dense vector embeddings using sentence-transformers.
    Model is loaded lazily and cached for the instance lifetime.

    Parameters
    ----------
    model_name : HuggingFace model ID compatible with sentence-transformers.
    device : PyTorch device (``"cpu"``, ``"cuda"``, ``"mps"``).
    batch_size : Texts per ``model.encode()`` call.
    max_workers : Kept for backwards-compatibility; no longer used.
                  sentence-transformers manages its own parallelism internally.
    normalize : If True, L2-normalize embeddings to unit vectors.
    """

    def __init__(
        self,
        *,
        model_name: str = _DEFAULT_MODEL,
        device: str = "cpu",
        batch_size: int = _DEFAULT_BATCH_SIZE,
        max_workers: int = 4,  # kept for API compatibility, not used
        normalize: bool = True,
    ) -> None:
        self._model_name = model_name
        self._device = device
        self._batch_size = batch_size
        self._normalize = normalize
        self._model = None  # lazy

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def embedding_dim(self) -> int:
        model = self._get_model()
        # Prefer the non-deprecated API; fall back for older versions
        if hasattr(model, "get_embedding_dimension"):
            dim = model.get_embedding_dimension()
        else:
            dim = model.get_sentence_embedding_dimension()
        return int(dim) if dim is not None else 384

    def embed(self, text: str) -> List[float]:
        """Embed a single text string."""
        model = self._get_model()
        vec = model.encode(
            text,
            normalize_embeddings=self._normalize,
            show_progress_bar=False,
        )
        return vec.tolist()

    def embed_batch(self, texts: Sequence[str]) -> List[List[float]]:
        """
        Embed multiple texts in a single vectorised ``model.encode()`` call.

        sentence-transformers already manages internal batching and uses
        optimised BLAS/OMP threads.  Using an additional ``ThreadPoolExecutor``
        on top causes CPU oversubscription and can reduce throughput, so we
        pass all texts at once and let the library handle parallelism.
        """
        if not texts:
            return []
        texts_list = list(texts)
        n = len(texts_list)
        logger.info("Embedding %d texts (batch_size=%d)", n, self._batch_size)

        model = self._get_model()
        embeddings = model.encode(
            texts_list,
            batch_size=self._batch_size,
            normalize_embeddings=self._normalize,
            show_progress_bar=False,
        )
        return [vec.tolist() for vec in embeddings]

    def get_model_info(self) -> Dict[str, object]:
        return {
            "model_name": self._model_name,
            "device": self._device,
            "embedding_dim": self.embedding_dim,
            "normalize": self._normalize,
            "batch_size": self._batch_size,
        }

    def _get_model(self):  # type: ignore[no-untyped-def]
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise ImportError(
                    "sentence-transformers required. Install: pip install sentence-transformers"
                ) from exc
            logger.info("Loading model '%s' on '%s'…", self._model_name, self._device)
            self._model = SentenceTransformer(self._model_name, device=self._device)
            logger.info("Model loaded — %d-dim.", self.embedding_dim)
        return self._model
