from importlib.resources.abc import Traversable
from pathlib import Path

from parsimonious.grammar import Grammar as ParsimoniousGrammar

from pa_record_retriever.pypdf.enum import DelimiterGlyph, FontWeight

_BASE_RULES = f"""
# Attributes
attr_light = attr_open coordinates light attr_close end_object
attr_regular = attr_open coordinates regular attr_close end_object
attr_bold = attr_open coordinates bold attr_close end_object
coordinates = digit+ separator digit+ separator digit+ separator

# Font weights
light = "{FontWeight.LIGHT}"
regular = "{FontWeight.REGULAR}"
bold = "{FontWeight.BOLD}"

# Characters
digit = ~r"[0-9]"
comma = ","
dot = "."
slash = "/"
space = " "
character = ~r"[^{repr(DelimiterGlyph.END_OBJECT.value).replace("'", "")}{DelimiterGlyph.RETURN}{DelimiterGlyph.ATTRIBUTES_OPEN}{DelimiterGlyph.ATTRIBUTES_CLOSE}]"

# Delimiters
separator = "|"
end_object = "{repr(DelimiterGlyph.END_OBJECT.value).replace("'", "")}"
return = "{DelimiterGlyph.RETURN}"
attr_open = "{DelimiterGlyph.ATTRIBUTES_OPEN}"
attr_close = "{DelimiterGlyph.ATTRIBUTES_CLOSE}"
"""


class Grammar(ParsimoniousGrammar):
    """Subclass of `parsimonious.Grammar` which takes a list of file paths to PEG
    grammar files as its input and appends delimiter variables from the `pypdf`
    module."""

    def __init__(self, rules: Path | Traversable | list[Path | Traversable]) -> None:
        """
        Initializes the grammar from one or more PEG grammar files.

        Files are read in order and concatenated, followed by ``_BASE_RULES`` which
        defines shared terminal rules (delimiters, font weights, character classes,
        etc.). The combined string is passed to ``parsimonious.Grammar``.

        Args:
            rules (Path | Traversable | list[Path | Traversable]): A single path or
                ordered list of paths to ``.peg`` grammar files. Accepts both
                ``pathlib.Path`` objects and ``importlib.resources`` traversables,
                allowing use with both file-system and zip-packaged distributions.
                When multiple files are provided, later files may reference rules
                defined in earlier ones.

        """
        if not isinstance(rules, list):
            rules = [rules]

        rules_content = ""

        for rule in rules:
            with open(rule) as f:
                rules_content += f.read() + "\n"

        super().__init__(rules_content + _BASE_RULES)
