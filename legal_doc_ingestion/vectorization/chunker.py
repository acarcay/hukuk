"""
Semantic chunking strategy for legal documents.

Instead of naive character-based splitting, this module splits text by
structural legal keywords (Article / Madde, Clause / Fıkra, Section / Bölüm,
Paragraph, etc.) while maintaining a configurable overlap between adjacent
chunks to preserve cross-boundary context.

Usage::

    from legal_doc_ingestion.vectorization.chunker import LegalSemanticChunker

    chunker = LegalSemanticChunker(overlap_ratio=0.10)
    chunks = chunker.chunk(cleaned_text, source_id="contract_v2.pdf")
"""

from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Pattern, Sequence


# ------------------------------------------------------------------
# Data model
# ------------------------------------------------------------------

@dataclass
class TextChunk:
    """A single semantically meaningful chunk of legal text."""

    chunk_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    text: str = ""
    source_id: str = ""
    chunk_index: int = 0
    total_chunks: int = 0
    section_heading: Optional[str] = None
    char_count: int = 0
    metadata: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.char_count = len(self.text)


# ------------------------------------------------------------------
# Legal heading patterns  (Turkish + English)
# ------------------------------------------------------------------

# Each pattern captures the *entire heading line* (group 0) so we can
# use it as the ``section_heading`` in the chunk metadata.
_LEGAL_HEADING_PATTERNS: List[Pattern[str]] = [
    # Turkish: MADDE 1, Madde 12 –, MADDE 1/A
    re.compile(
        r"(?im)^[ \t]*(MADDE|Madde)\s+\d+[\s/A-Za-zÇçĞğİıÖöŞşÜü]*\s*[-–—:]?.*$"
    ),
    # English: Article 1, ARTICLE IV
    re.compile(
        r"(?im)^[ \t]*(ARTICLE|Article)\s+[IVXLCDM\d]+[\s.)\-–—:]*.*$"
    ),
    # Section / Bölüm
    re.compile(
        r"(?im)^[ \t]*(SECTION|Section|BÖLÜM|Bölüm)\s+[IVXLCDM\d]+[\s.)\-–—:]*.*$"
    ),
    # Clause / Fıkra
    re.compile(
        r"(?im)^[ \t]*(CLAUSE|Clause|FIKRA|Fıkra)\s+\d+[\s.)\-–—:]*.*$"
    ),
    # Part / Kısım
    re.compile(
        r"(?im)^[ \t]*(PART|Part|KISIM|Kısım)\s+[IVXLCDM\d]+[\s.)\-–—:]*.*$"
    ),
    # Chapter / Fasıl
    re.compile(
        r"(?im)^[ \t]*(CHAPTER|Chapter|FASIL|Fasıl)\s+[IVXLCDM\d]+[\s.)\-–—:]*.*$"
    ),
    # GEÇİCİ MADDE (Provisional Article – common in Turkish law)
    re.compile(
        r"(?im)^[ \t]*(GEÇİCİ\s+MADDE|Geçici\s+Madde)\s+\d+[\s/A-Za-zÇçĞğİıÖöŞşÜü]*\s*[-–—:]?.*$"
    ),
    # Numbered paragraphs like "1.", "1)", "(1)"
    re.compile(
        r"(?im)^[ \t]*\(?(\d{1,3})[.)]\s+.{10,}$"
    ),
]


class LegalSemanticChunker:
    """
    Splits cleaned legal text into semantically coherent chunks based on
    structural headings (Article, Clause, Section, …).

    Parameters
    ----------
    overlap_ratio : float
        Fraction of the **previous** chunk's tail to prepend to the next
        chunk.  Default ``0.10`` (10 %).
    min_chunk_chars : int
        Chunks shorter than this are merged into the preceding chunk.
    max_chunk_chars : int
        If a single section exceeds this, it is sub-split at sentence
        boundaries to keep chunk sizes manageable.
    heading_patterns : list, optional
        Override the built-in legal heading regex patterns.
    """

    def __init__(
        self,
        *,
        overlap_ratio: float = 0.10,
        min_chunk_chars: int = 100,
        max_chunk_chars: int = 3000,
        heading_patterns: Optional[List[Pattern[str]]] = None,
    ) -> None:
        if not 0.0 <= overlap_ratio < 1.0:
            raise ValueError("overlap_ratio must be in [0.0, 1.0)")
        self._overlap_ratio = overlap_ratio
        self._min_chars = min_chunk_chars
        self._max_chars = max_chunk_chars
        self._patterns = heading_patterns or _LEGAL_HEADING_PATTERNS

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def chunk(
        self,
        text: str,
        source_id: str = "",
        extra_metadata: Optional[Dict[str, str]] = None,
    ) -> List[TextChunk]:
        """
        Split *text* into semantic chunks.

        Parameters
        ----------
        text
            The cleaned legal document text (all pages concatenated).
        source_id
            Identifier for the source document (e.g. filename).
        extra_metadata
            Arbitrary key-value pairs attached to every chunk.

        Returns
        -------
        list[TextChunk]
            Ordered list of chunks with overlap applied.
        """
        if not text or not text.strip():
            return []

        # Step 1: find all heading positions
        raw_sections = self._split_at_headings(text)

        # Step 2: merge tiny sections into their predecessor
        merged = self._merge_small_sections(raw_sections)

        # Step 3: sub-split oversized sections
        split = self._subsplit_large_sections(merged)

        # Step 4: apply overlap
        overlapped = self._apply_overlap(split)

        # Step 5: build TextChunk objects
        total = len(overlapped)
        meta = extra_metadata or {}
        chunks: List[TextChunk] = []

        for idx, (heading, body) in enumerate(overlapped):
            chunk_text = body.strip()
            if not chunk_text:
                continue
            chunks.append(
                TextChunk(
                    chunk_id=self._deterministic_id(source_id, idx),
                    text=chunk_text,
                    source_id=source_id,
                    chunk_index=idx,
                    total_chunks=total,
                    section_heading=heading,
                    metadata=dict(meta),
                )
            )

        # Fix total_chunks after possible empty-drops
        for c in chunks:
            c.total_chunks = len(chunks)

        return chunks

    # ------------------------------------------------------------------
    # Internal: splitting
    # ------------------------------------------------------------------

    def _split_at_headings(
        self, text: str
    ) -> List[tuple]:
        """
        Return a list of ``(heading_or_None, section_body)`` tuples by
        scanning for legal heading patterns.
        """
        # Collect all heading match positions
        headings: List[tuple] = []  # (start, end, matched_text)
        for pat in self._patterns:
            for m in pat.finditer(text):
                headings.append((m.start(), m.end(), m.group(0).strip()))

        if not headings:
            # No structural headings found → return entire text as one section
            return [(None, text)]

        # Sort by position, deduplicate overlapping matches (keep earliest)
        headings.sort(key=lambda h: h[0])
        deduped: List[tuple] = [headings[0]]
        for h in headings[1:]:
            if h[0] >= deduped[-1][1]:
                deduped.append(h)

        sections: List[tuple] = []

        # Text before the first heading (preamble)
        if deduped[0][0] > 0:
            preamble = text[: deduped[0][0]]
            if preamble.strip():
                sections.append((None, preamble))

        # Each heading → next heading (or end)
        for i, (start, end, heading_text) in enumerate(deduped):
            body_start = end
            body_end = deduped[i + 1][0] if i + 1 < len(deduped) else len(text)
            body = text[body_start:body_end]
            sections.append((heading_text, body))

        return sections

    def _merge_small_sections(
        self, sections: List[tuple]
    ) -> List[tuple]:
        """Merge sections shorter than ``min_chunk_chars`` into the previous."""
        if not sections:
            return sections

        merged: List[tuple] = [sections[0]]
        for heading, body in sections[1:]:
            if len(body.strip()) < self._min_chars and merged:
                prev_heading, prev_body = merged[-1]
                joiner = f"\n{heading}\n" if heading else "\n"
                merged[-1] = (prev_heading, prev_body + joiner + body)
            else:
                merged.append((heading, body))
        return merged

    def _subsplit_large_sections(
        self, sections: List[tuple]
    ) -> List[tuple]:
        """Sub-split sections exceeding ``max_chunk_chars`` at sentence boundaries."""
        result: List[tuple] = []
        for heading, body in sections:
            if len(body) <= self._max_chars:
                result.append((heading, body))
                continue
            sub_chunks = self._split_at_sentences(body, self._max_chars)
            for i, sub in enumerate(sub_chunks):
                sub_heading = f"{heading} (part {i + 1})" if heading else None
                result.append((sub_heading, sub))
        return result

    # ------------------------------------------------------------------
    # Internal: overlap
    # ------------------------------------------------------------------

    def _apply_overlap(
        self, sections: List[tuple]
    ) -> List[tuple]:
        """Prepend the trailing ``overlap_ratio`` fraction of the previous chunk."""
        if self._overlap_ratio <= 0.0 or len(sections) <= 1:
            return sections

        result: List[tuple] = [sections[0]]
        for i in range(1, len(sections)):
            prev_body = sections[i - 1][1]
            overlap_len = int(len(prev_body) * self._overlap_ratio)
            if overlap_len > 0:
                overlap_text = prev_body[-overlap_len:]
                # Try to start at a word boundary
                space_idx = overlap_text.find(" ")
                if space_idx != -1:
                    overlap_text = overlap_text[space_idx + 1:]
                heading, body = sections[i]
                body = overlap_text + "\n" + body
                result.append((heading, body))
            else:
                result.append(sections[i])
        return result

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _split_at_sentences(text: str, max_len: int) -> List[str]:
        """Split *text* at sentence-ending punctuation into segments ≤ *max_len*."""
        sentence_ends = re.compile(r"(?<=[.!?;])\s+")
        sentences = sentence_ends.split(text)
        chunks: List[str] = []
        current: List[str] = []
        current_len = 0

        for sent in sentences:
            if current_len + len(sent) > max_len and current:
                chunks.append(" ".join(current))
                current = []
                current_len = 0
            current.append(sent)
            current_len += len(sent) + 1

        if current:
            chunks.append(" ".join(current))
        return chunks

    @staticmethod
    def _deterministic_id(source_id: str, index: int) -> str:
        """Generate a reproducible chunk ID from source + index."""
        raw = f"{source_id}::chunk::{index}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]
