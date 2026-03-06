from pathlib import Path

import pytest
from parsimonious.exceptions import ParseError

from pa_record_retriever.parsimonious.grammar import Grammar


class TestGrammar:
    """Tests for the ``Grammar`` class."""

    def test_instantiates_from_single_path(self, tmp_path: Path) -> None:
        """A single ``Path`` is accepted without error."""
        peg_file = tmp_path / "test.peg"
        peg_file.write_text('root = ~r"[a-z]+"\n')
        grammar = Grammar(peg_file)
        assert grammar is not None

    def test_instantiates_from_list_of_paths(self, tmp_path: Path) -> None:
        """A list of ``Path`` objects is accepted without error."""
        peg_file1 = tmp_path / "part1.peg"
        peg_file2 = tmp_path / "part2.peg"
        peg_file1.write_text("root = greeting\n")
        peg_file2.write_text('greeting = ~r"[a-z]+"\n')
        grammar = Grammar([peg_file1, peg_file2])
        assert grammar is not None

    def test_single_path_converted_to_list_internally(self, tmp_path: Path) -> None:
        """A single path is wrapped in a list and the resulting grammar parses
        correctly."""
        peg_file = tmp_path / "test.peg"
        peg_file.write_text('root = ~r"[a-z]+"\n')
        grammar = Grammar(peg_file)
        result = grammar.parse("hello")
        assert result is not None

    def test_base_rules_available_in_custom_grammar(self, tmp_path: Path) -> None:
        """Base rules such as ``character`` are accessible in custom grammar files."""
        peg_file = tmp_path / "test.peg"
        peg_file.write_text("root = character+\n")
        grammar = Grammar(peg_file)
        result = grammar.parse("hello")
        assert result is not None

    def test_multiple_files_rules_combined(self, tmp_path: Path) -> None:
        """Rules from multiple files are combined into a single grammar."""
        peg_file1 = tmp_path / "part1.peg"
        peg_file2 = tmp_path / "part2.peg"
        peg_file1.write_text("root = greeting\n")
        peg_file2.write_text('greeting = ~r"[a-z]+"\n')
        grammar = Grammar([peg_file1, peg_file2])
        result = grammar.parse("hello")
        assert result is not None

    def test_later_file_can_reference_earlier_rules(self, tmp_path: Path) -> None:
        """Rules defined in an earlier file are referenceable from a later file."""
        peg_file1 = tmp_path / "shared.peg"
        peg_file2 = tmp_path / "main.peg"
        peg_file1.write_text('word = ~r"[a-z]+"\n')
        peg_file2.write_text("root = word\n")
        grammar = Grammar([peg_file1, peg_file2])
        result = grammar.parse("test")
        assert result.text == "test"

    def test_parse_fails_on_non_matching_input(self, tmp_path: Path) -> None:
        """A ``ParseError`` is raised when the input does not satisfy the grammar."""
        peg_file = tmp_path / "test.peg"
        peg_file.write_text('root = ~r"[0-9]+"\n')
        grammar = Grammar(peg_file)
        with pytest.raises(ParseError):
            grammar.parse("abc")

    def test_empty_additional_file_does_not_break(self, tmp_path: Path) -> None:
        """An empty additional file does not prevent the grammar from compiling."""
        peg_file1 = tmp_path / "main.peg"
        peg_file2 = tmp_path / "empty.peg"
        peg_file1.write_text('root = ~r"[a-z]+"\n')
        peg_file2.write_text("")
        grammar = Grammar([peg_file1, peg_file2])
        assert grammar.parse("hello") is not None
