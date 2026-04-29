"""
Abstract base class for all document parsers.

Every format-specific parser must implement ``parse()`` and return a list
of ``RawPage`` objects, which the ingestion layer will then clean and
assemble into the final ``DocumentResult``.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class RawPage:
    """Intermediate representation of a single page before cleaning."""

    page_number: int
    text: str
    ocr_applied: bool = False
    ocr_confidence: Optional[float] = None


@dataclass
class RawDocument:
    """Intermediate representation of a full document before cleaning."""

    pages: List[RawPage] = field(default_factory=list)
    author: Optional[str] = None
    title: Optional[str] = None
    creation_date: Optional[str] = None
    warnings: List[str] = field(default_factory=list)


class BaseParser(abc.ABC):
    """
    Abstract parser interface.

    Subclasses must override ``parse`` and ``supported_extensions``.
    """

    @abc.abstractmethod
    def parse(self, filepath: Path) -> RawDocument:
        """
        Parse the given file and return a ``RawDocument``.

        Raises
        ------
        CorruptedFileError
            If the file cannot be opened.
        ParsingError
            If content extraction fails after opening.
        """

    @property
    @abc.abstractmethod
    def supported_extensions(self) -> set[str]:
        """Return the set of lowercase extensions this parser handles (e.g. ``{'.pdf'}``)."""
