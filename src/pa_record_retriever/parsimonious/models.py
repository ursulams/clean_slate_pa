from __future__ import annotations

import importlib.resources
import io
from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar

from pypdf import PdfReader

from pa_record_retriever import __name__ as __package_name__
from pa_record_retriever.parsimonious.grammar import Grammar
from pa_record_retriever.parsimonious.nodes import NodeVisitor
from pa_record_retriever.pydantic import BaseModel
from pa_record_retriever.pypdf.reader import Page


class ParsedDocument(BaseModel, ABC):
    """Abstract base class for models parsed from PDF documents using a PEG grammar."""

    _peg_path: ClassVar[Path]
    """
    Path to the PEG grammar file, relative to the package root.

    Must be set by concrete subclasses.

    """

    @classmethod
    def visitor(cls) -> NodeVisitor:
        """
        Returns a ``NodeVisitor`` subclass configured for this document type.

        Dynamically creates a ``ParsedDocumentVisitor`` with ``model_class`` set to
        ``cls``, so visit methods are generated from this class's field annotations.

        """

        class ParsedDocumentVisitor(NodeVisitor):
            model_class = cls

        return ParsedDocumentVisitor()

    @classmethod
    def grammar(cls) -> Grammar:
        """
        Returns a ``Grammar`` instance loaded from ``_peg_path``.

        Resolves the path relative to the package root using ``importlib.resources``
        and passes it to ``Grammar``.

        """
        grammar_path = importlib.resources.files(__package_name__).joinpath(str(cls._peg_path))

        return Grammar(grammar_path)

    @staticmethod
    @abstractmethod
    def _preprocess(text: str) -> str:
        """
        Preprocesses raw extracted text from the PDF before parsing.

        Args:
            text: The raw extracted text.

        Returns:
            str: The preprocessed text.

        """
        pass

    @classmethod
    def from_bytes(cls, pdf: bytes) -> ParsedDocument:
        """
        Parses a PDF document from its byte content.

        Args:
            pdf: The byte content of the PDF document.

        Returns:
            ParsedDocument: An instance of the parsed document model.

        """
        reader = PdfReader(io.BytesIO(pdf))

        text = ""
        for _page in reader.pages:
            page = Page(pdf, _page)
            text += page.extract_text()

        text = cls._preprocess(text)

        grammar = cls.grammar()
        tree = grammar.parse(text)

        visitor = cls.visitor()
        return visitor.serialize(tree)
