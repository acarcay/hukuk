"""
Embedding generation engine using a lightweight, multilingual
sentence-transformer model suitable for local execution.

Default model: ``paraphrase-multilingual-MiniLM-L12-v2``
  - 118M params, ~470 MB, 50+ languages (incl. Turkish)
  - 384-dimensional embeddings, fast CPU inference

Uses ThreadPoolExecutor for batch embedding with configurable concurrency.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
_DEFAULT_BATCH_SIZE = 64
_DEFAULT_WORKERS = 4


class EmbeddingEngine:
    """
    Generates dense vector embeddings using sentence-transformers.
    Model is loaded lazily and cached for the instance lifetime.

    Parameters
    ----------
    model_name : HuggingFace model ID compatible with sentence-transformers.
    device : PyTorch device (``"cpu"``, ``"cuda"``, ``"mps"``).
    batch_size : Texts per encoding call inside each thread.
    max_workers : Thread pool size for ``embed_batch``.
    normalize : If True, L2-normalize embeddings to unit vectors.
    """

    def __init__(
        self,
        *,
        model_name: str = _DEFAULT_MODEL,
        device: str = "cpu",
        batch_size: int = _DEFAULT_BATCH_SIZE,
        max_workers: int = _DEFAULT_WORKERS,
        normalize: bool = True,
    ) -> None:
        self._model_name = model_name
        self._device = device
        self._batch_size = batch_size
        self._max_workers = max_workers
        self._normalize = normalize
        self._model = None  # lazy

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def embedding_dim(self) -> int:
        model = self._get_model()
        dim = model.get_sentence_embedding_dimension()
        return int(dim) if dim is not None else 384

    def embed(self, text: str) -> List[float]:
        """Embed a single text string."""
        model = self._get_model()
        vec = model.encode(text, normalize_embeddings=self._normalize, show_progress_bar=False)
        return vec.tolist()

    def embed_batch(self, texts: Sequence[str]) -> List[List[float]]:
        """
        Embed multiple texts using multithreading.

        Texts are partitioned into sub-batches and encoded in parallel.
        Each thread calls model.encode() which releases the GIL during
        the underlying forward pass.
        """
        if not texts:
            return []
        n = len(texts)
        logger.info("Embedding %d texts (batch=%d, workers=%d)", n, self._batch_size, self._max_workers)

        sub_batches: List[tuple] = []
        for start in range(0, n, self._batch_size):
            end = min(start + self._batch_size, n)
            sub_batches.append((start, list(texts[start:end])))

        results: List[Optional[List[float]]] = [None] * n

        if len(sub_batches) == 1:
            vecs = self._encode_sub_batch(sub_batches[0][1])
            for i, v in enumerate(vecs):
                results[sub_batches[0][0] + i] = v
        else:
            with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
                future_map = {
                    pool.submit(self._encode_sub_batch, batch): start
                    for start, batch in sub_batches
                }
                for future in as_completed(future_map):
                    start_idx = future_map[future]
                    vecs = future.result()
                    for i, v in enumerate(vecs):
                        results[start_idx + i] = v

        missing = [i for i, r in enumerate(results) if r is None]
        if missing:
            raise RuntimeError(f"Embedding failed for indices: {missing[:20]}")
        return results  # type: ignore[return-value]

    def get_model_info(self) -> Dict[str, object]:
        return {
            "model_name": self._model_name, "device": self._device,
            "embedding_dim": self.embedding_dim, "normalize": self._normalize,
            "batch_size": self._batch_size, "max_workers": self._max_workers,
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
            logger.info("Model loaded — %d-dim.", self._model.get_sentence_embedding_dimension())
        return self._model

    def _encode_sub_batch(self, texts: List[str]) -> List[List[float]]:
        model = self._get_model()
        embeddings = model.encode(
            texts, normalize_embeddings=self._normalize,
            show_progress_bar=False, batch_size=len(texts),
        )
        return [vec.tolist() for vec in embeddings]
