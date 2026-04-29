"""
Text cleaning utilities tailored for legal documents.

Handles removal of:
  - Watermarks and confidentiality banners
  - Redundant / excessive line breaks
  - Page numbers and page-break artifacts
  - Common header/footer noise
"""

from __future__ import annotations

import re
from typing import Callable, List, Optional, Tuple


class TextCleaner:
    """
    Configurable text-cleaning pipeline for legal document text.

    The cleaner applies a chain of transformations in a deterministic order.
    You can extend the pipeline by registering custom cleaning functions via
    ``add_step()``.

    Usage::

        cleaner = TextCleaner()
        clean = cleaner.clean("RAW TEXT HERE…")
    """

    # Common watermark / confidentiality patterns in legal docs
    _WATERMARK_PATTERNS: list[re.Pattern[str]] = [
        re.compile(r"(?i)\bconfidential\b"),
        re.compile(r"(?i)\bdraft\b"),
        re.compile(r"(?i)\bprivileged\b"),
        re.compile(r"(?i)\bdo\s+not\s+copy\b"),
        re.compile(r"(?i)\bfor\s+internal\s+use\s+only\b"),
        re.compile(r"(?i)\bwatermark\b"),
        re.compile(r"(?i)\bsample\s+document\b"),
        re.compile(r"(?i)\bunofficial\s+copy\b"),
    ]

    # Page-number patterns — standalone lines like "Page 3 of 10", "- 7 -", "3"
    _PAGE_NUMBER_PATTERNS: list[re.Pattern[str]] = [
        re.compile(r"(?im)^\s*page\s+\d+\s*(of\s+\d+)?\s*$"),
        re.compile(r"(?im)^\s*-\s*\d+\s*-\s*$"),
        re.compile(r"(?im)^\s*\d{1,4}\s*$"),             # bare number on its own line
        re.compile(r"(?im)^\s*sayfa\s+\d+\s*/?\s*\d*\s*$"),  # Turkish «Sayfa 3/10»
    ]

    # Header/footer noise commonly repeated on every page
    _HEADER_FOOTER_PATTERNS: list[re.Pattern[str]] = [
        re.compile(r"(?im)^\s*https?://\S+\s*$"),        # stray URLs
        re.compile(r"(?im)^\s*www\.\S+\s*$"),
    ]

    def __init__(self, *, extra_watermarks: Optional[List[str]] = None) -> None:
        """
        Parameters
        ----------
        extra_watermarks
            Additional watermark strings/regex patterns to strip beyond defaults.
        """
        self._extra_watermark_patterns: list[re.Pattern[str]] = []
        if extra_watermarks:
            for pat in extra_watermarks:
                self._extra_watermark_patterns.append(
                    re.compile(pat, re.IGNORECASE)
                )

        # Ordered pipeline of (name, callable) tuples
        self._pipeline: list[tuple[str, Callable[[str], str]]] = [
            ("remove_null_bytes", self._remove_null_bytes),
            ("normalize_unicode", self._normalize_unicode),
            ("remove_watermarks", self._remove_watermarks),
            ("remove_page_numbers", self._remove_page_numbers),
            ("remove_header_footer_noise", self._remove_header_footer_noise),
            ("normalize_whitespace", self._normalize_whitespace),
            ("strip", str.strip),
        ]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def clean(self, text: str) -> str:
        """Run the full cleaning pipeline on *text* and return the result."""
        for _name, fn in self._pipeline:
            text = fn(text)
        return text

    def add_step(
        self,
        name: str,
        fn: Callable[[str], str],
        *,
        position: Optional[int] = None,
    ) -> None:
        """
        Register a custom cleaning step.

        Parameters
        ----------
        name
            Human-readable identifier (used for logging/debugging).
        fn
            A callable that accepts a string and returns a cleaned string.
        position
            Insert position in the pipeline (0-indexed). ``None`` appends to the end.
        """
        entry = (name, fn)
        if position is None:
            self._pipeline.append(entry)
        else:
            self._pipeline.insert(position, entry)

    # ------------------------------------------------------------------
    # Built-in cleaning steps
    # ------------------------------------------------------------------

    @staticmethod
    def _remove_null_bytes(text: str) -> str:
        """Strip null bytes that sometimes appear in OCR or RTF output."""
        return text.replace("\x00", "")

    @staticmethod
    def _normalize_unicode(text: str) -> str:
        """Normalize common Unicode quirks (smart quotes, em-dashes, etc.)."""
        replacements: dict[str, str] = {
            "\u2018": "'",   # left single quote
            "\u2019": "'",   # right single quote
            "\u201c": '"',   # left double quote
            "\u201d": '"',   # right double quote
            "\u2013": "-",   # en-dash
            "\u2014": "-",   # em-dash
            "\u00a0": " ",   # non-breaking space
            "\u200b": "",    # zero-width space
            "\ufeff": "",    # BOM
        }
        for orig, repl in replacements.items():
            text = text.replace(orig, repl)
        return text

    def _remove_watermarks(self, text: str) -> str:
        """Remove lines that consist *solely* of a known watermark pattern."""
        lines = text.split("\n")
        cleaned: list[str] = []
        all_patterns = self._WATERMARK_PATTERNS + self._extra_watermark_patterns
        for line in lines:
            stripped = line.strip()
            if stripped and any(p.fullmatch(stripped) for p in all_patterns):
                continue  # drop watermark-only lines
            cleaned.append(line)
        return "\n".join(cleaned)

    def _remove_page_numbers(self, text: str) -> str:
        """Remove standalone page-number lines."""
        for pat in self._PAGE_NUMBER_PATTERNS:
            text = pat.sub("", text)
        return text

    def _remove_header_footer_noise(self, text: str) -> str:
        """Remove recurring header/footer artefacts."""
        for pat in self._HEADER_FOOTER_PATTERNS:
            text = pat.sub("", text)
        return text

    @staticmethod
    def _normalize_whitespace(text: str) -> str:
        """
        Collapse runs of 3+ newlines into exactly 2 (preserving paragraph breaks)
        and strip trailing spaces on each line.
        """
        # Strip trailing whitespace per line
        text = re.sub(r"[ \t]+$", "", text, flags=re.MULTILINE)
        # Collapse excessive blank lines
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text
