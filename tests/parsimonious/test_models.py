import io
from pathlib import Path
from typing import ClassVar
from unittest.mock import MagicMock, patch

import pytest

from pa_record_retriever.parsimonious.grammar import Grammar
from pa_record_retriever.parsimonious.models import ParsedDocument
from pa_record_retriever.parsimonious.nodes import NodeVisitor


class _SimpleDoc(ParsedDocument):
    """A minimal concrete ``ParsedDocument`` subclass used across multiple tests."""

    _peg_path: ClassVar[Path] = Path("grammars/shared.peg")

    name: str

    @staticmethod
    def _preprocess(text: str) -> str:
        """Returns the input text unchanged."""
        return text


class TestParsedDocument:
    """Tests for the ``ParsedDocument`` abstract base class."""

    class TestVisitor:
        """Tests for ``ParsedDocument.visitor``."""

        def test_returns_node_visitor_instance(self) -> None:
            """``visitor()`` returns an instance of ``NodeVisitor``."""
            assert isinstance(_SimpleDoc.visitor(), NodeVisitor)

        def test_visitor_model_class_is_document_class(self) -> None:
            """The returned visitor has ``model_class`` set to the calling class."""
            assert _SimpleDoc.visitor().model_class is _SimpleDoc

        def test_each_call_returns_fresh_instance(self) -> None:
            """Each call to ``visitor()`` returns a distinct object."""
            v1 = _SimpleDoc.visitor()
            v2 = _SimpleDoc.visitor()
            assert v1 is not v2

        def test_visitor_subclass_name_is_parsed_document_visitor(self) -> None:
            """The generated visitor class is named ``ParsedDocumentVisitor``."""
            visitor = _SimpleDoc.visitor()
            assert type(visitor).__name__ == "ParsedDocumentVisitor"

    class TestGrammar:
        """Tests for ``ParsedDocument.grammar``."""

        def test_returns_grammar_instance(self, tmp_path: Path) -> None:
            """``grammar()`` returns a ``Grammar`` instance."""
            peg_file = tmp_path / "test.peg"
            peg_file.write_text("root = name\nname = character+\n")

            class Doc(ParsedDocument):
                """Minimal doc for grammar instance test."""

                _peg_path: ClassVar[Path] = peg_file
                name: str

                @staticmethod
                def _preprocess(text: str) -> str:
                    """Returns text unchanged."""
                    return text

            with patch("pa_record_retriever.parsimonious.models.importlib") as mock_importlib:
                mock_importlib.resources.files.return_value.joinpath.return_value = peg_file
                grammar = Doc.grammar()

            assert isinstance(grammar, Grammar)

        def test_grammar_uses_peg_path(self, tmp_path: Path) -> None:
            """The grammar returned by ``grammar()`` successfully parses matching
            input."""
            peg_file = tmp_path / "doc.peg"
            peg_file.write_text('root = ~r"[a-z]+"\n')

            class Doc(ParsedDocument):
                """Minimal doc for grammar path test."""

                _peg_path: ClassVar[Path] = peg_file
                name: str

                @staticmethod
                def _preprocess(text: str) -> str:
                    """Returns text unchanged."""
                    return text

            with patch("pa_record_retriever.parsimonious.models.importlib") as mock_importlib:
                mock_importlib.resources.files.return_value.joinpath.return_value = peg_file
                grammar = Doc.grammar()

            assert grammar.parse("hello") is not None

    class TestPreprocess:
        """Tests for ``ParsedDocument._preprocess``."""

        def test_preprocess_is_abstract(self) -> None:
            """``ParsedDocument`` cannot be instantiated directly because
            ``_preprocess`` is abstract."""
            with pytest.raises(TypeError):
                ParsedDocument()

        def test_concrete_preprocess_called(self) -> None:
            """``_preprocess`` is called with the raw extracted text during
            ``from_bytes``."""
            called_with: list[str] = []

            class Doc(ParsedDocument):
                """Minimal doc for preprocess invocation test."""

                _peg_path: ClassVar[Path] = Path("grammars/shared.peg")
                name: str

                @staticmethod
                def _preprocess(text: str) -> str:
                    """Records invocation and returns text unchanged."""
                    called_with.append(text)
                    return text

            with (
                patch("pa_record_retriever.parsimonious.models.PdfReader") as mock_reader_cls,
                patch("pa_record_retriever.parsimonious.models.Page") as mock_page_cls,
                patch.object(Doc, "grammar") as mock_grammar_fn,
                patch.object(Doc, "visitor") as mock_visitor_fn,
            ):
                mock_reader = MagicMock()
                mock_page = MagicMock()
                mock_page.extract_text.return_value = "raw text"
                mock_reader.pages = [mock_page]
                mock_reader_cls.return_value = mock_reader
                mock_page_cls.return_value = mock_page

                mock_grammar = MagicMock()
                mock_grammar.parse.return_value = MagicMock()
                mock_grammar_fn.return_value = mock_grammar

                mock_visitor = MagicMock()
                mock_visitor.serialize.return_value = MagicMock()
                mock_visitor_fn.return_value = mock_visitor

                Doc.from_bytes(b"fake pdf")

            assert "raw text" in called_with

    class TestFromBytes:
        """Tests for ``ParsedDocument.from_bytes``."""

        def test_returns_serialized_result(self) -> None:
            """``from_bytes`` returns the object produced by ``visitor.serialize``."""

            class Doc(ParsedDocument):
                """Minimal doc for serialized result test."""

                _peg_path: ClassVar[Path] = Path("grammars/shared.peg")
                name: str

                @staticmethod
                def _preprocess(text: str) -> str:
                    """Returns text unchanged."""
                    return text

            mock_result = MagicMock()

            with (
                patch("pa_record_retriever.parsimonious.models.PdfReader") as mock_reader_cls,
                patch("pa_record_retriever.parsimonious.models.Page") as mock_page_cls,
                patch.object(Doc, "grammar") as mock_grammar_fn,
                patch.object(Doc, "visitor") as mock_visitor_fn,
            ):
                mock_reader = MagicMock()
                mock_page = MagicMock()
                mock_page.extract_text.return_value = "page text"
                mock_reader.pages = [mock_page]
                mock_reader_cls.return_value = mock_reader
                mock_page_cls.return_value = mock_page

                mock_grammar = MagicMock()
                mock_tree = MagicMock()
                mock_grammar.parse.return_value = mock_tree
                mock_grammar_fn.return_value = mock_grammar

                mock_visitor = MagicMock()
                mock_visitor.serialize.return_value = mock_result
                mock_visitor_fn.return_value = mock_visitor

                result = Doc.from_bytes(b"fake pdf bytes")

            assert result is mock_result

        def test_concatenates_text_from_all_pages(self) -> None:
            """Text from all pages is concatenated before being passed to
            ``grammar.parse``."""

            class Doc(ParsedDocument):
                """Minimal doc for page concatenation test."""

                _peg_path: ClassVar[Path] = Path("grammars/shared.peg")
                name: str

                @staticmethod
                def _preprocess(text: str) -> str:
                    """Returns text unchanged."""
                    return text

            parsed_texts: list[str] = []

            with (
                patch("pa_record_retriever.parsimonious.models.PdfReader") as mock_reader_cls,
                patch("pa_record_retriever.parsimonious.models.Page") as mock_page_cls,
                patch.object(Doc, "grammar") as mock_grammar_fn,
                patch.object(Doc, "visitor") as mock_visitor_fn,
            ):
                mock_reader = MagicMock()
                page1 = MagicMock()
                page1.extract_text.return_value = "page one "
                page2 = MagicMock()
                page2.extract_text.return_value = "page two"
                mock_reader.pages = [page1, page2]
                mock_reader_cls.return_value = mock_reader
                mock_page_cls.side_effect = lambda pdf, p: p

                mock_grammar = MagicMock()

                def capture_parse(text: str) -> MagicMock:
                    """Captures the text passed to ``grammar.parse``."""
                    parsed_texts.append(text)
                    return MagicMock()

                mock_grammar.parse.side_effect = capture_parse
                mock_grammar_fn.return_value = mock_grammar

                mock_visitor = MagicMock()
                mock_visitor.serialize.return_value = MagicMock()
                mock_visitor_fn.return_value = mock_visitor

                Doc.from_bytes(b"fake pdf")

            assert len(parsed_texts) == 1
            assert parsed_texts[0] == "page one page two"

        def test_wraps_bytes_in_bytes_io_for_reader(self) -> None:
            """The PDF bytes are wrapped in ``io.BytesIO`` before being passed to
            ``PdfReader``."""

            class Doc(ParsedDocument):
                """Minimal doc for BytesIO wrapping test."""

                _peg_path: ClassVar[Path] = Path("grammars/shared.peg")
                name: str

                @staticmethod
                def _preprocess(text: str) -> str:
                    """Returns text unchanged."""
                    return text

            received_args: list[object] = []

            with (
                patch("pa_record_retriever.parsimonious.models.PdfReader") as mock_reader_cls,
                patch("pa_record_retriever.parsimonious.models.Page") as mock_page_cls,
                patch.object(Doc, "grammar") as mock_grammar_fn,
                patch.object(Doc, "visitor") as mock_visitor_fn,
            ):
                mock_reader = MagicMock()
                mock_reader.pages = []
                mock_reader_cls.side_effect = lambda arg: received_args.append(arg) or mock_reader

                mock_page_cls.return_value = MagicMock()

                mock_grammar = MagicMock()
                mock_grammar.parse.return_value = MagicMock()
                mock_grammar_fn.return_value = mock_grammar

                mock_visitor = MagicMock()
                mock_visitor.serialize.return_value = MagicMock()
                mock_visitor_fn.return_value = mock_visitor

                Doc.from_bytes(b"pdf content")

            assert len(received_args) == 1
            assert isinstance(received_args[0], io.BytesIO)

        def test_visitor_serialize_called_with_parsed_tree(self) -> None:
            """``visitor.serialize`` is called exactly once with the tree returned by
            ``grammar.parse``."""

            class Doc(ParsedDocument):
                """Minimal doc for serialize-call-args test."""

                _peg_path: ClassVar[Path] = Path("grammars/shared.peg")
                name: str

                @staticmethod
                def _preprocess(text: str) -> str:
                    """Returns text unchanged."""
                    return text

            with (
                patch("pa_record_retriever.parsimonious.models.PdfReader") as mock_reader_cls,
                patch("pa_record_retriever.parsimonious.models.Page") as mock_page_cls,
                patch.object(Doc, "grammar") as mock_grammar_fn,
                patch.object(Doc, "visitor") as mock_visitor_fn,
            ):
                mock_reader = MagicMock()
                mock_reader.pages = []
                mock_reader_cls.return_value = mock_reader
                mock_page_cls.return_value = MagicMock()

                mock_tree = MagicMock()
                mock_grammar = MagicMock()
                mock_grammar.parse.return_value = mock_tree
                mock_grammar_fn.return_value = mock_grammar

                mock_visitor = MagicMock()
                mock_visitor.serialize.return_value = MagicMock()
                mock_visitor_fn.return_value = mock_visitor

                Doc.from_bytes(b"pdf")

            mock_visitor.serialize.assert_called_once_with(mock_tree)
