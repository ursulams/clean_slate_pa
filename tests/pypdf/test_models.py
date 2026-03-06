from unittest.mock import MagicMock, patch

import pytest
from pypdf.generic import IndirectObject, NameObject

from pa_record_retriever.pypdf.enum import DelimiterGlyph, FontWeight
from pa_record_retriever.pypdf.models import BoundingBox, Font, TextObject, Type1FontDictionary


class _FakeFontDict(IndirectObject):
    """Minimal ``IndirectObject`` subclass used to satisfy Pydantic's
    ``font_dictionary`` type check."""

    _base_font: str

    def __init__(self, base_font: str = "ArialMT") -> None:
        """Initialises without a real PDF reader."""
        self._base_font = base_font

    def __getitem__(self, key: str) -> str:
        """Returns the stored base font name for any key."""
        return self._base_font


class TestType1FontDictionary:
    """Tests for the ``Type1FontDictionary`` Pydantic model."""

    class TestValidateSubtype:
        """Tests for ``Type1FontDictionary.validate_subtype``."""

        def test_name_object_converted_to_string(self) -> None:
            """A ``NameObject`` value is converted to a plain ``str``."""
            result = Type1FontDictionary.validate_subtype(NameObject("/Type1"))
            assert result == "/Type1"
            assert isinstance(result, str)

        def test_non_name_object_returns_none(self) -> None:
            """A non-``NameObject`` value is returned unchanged."""
            result = Type1FontDictionary.validate_subtype("/Type1")
            assert result == "/Type1"


class TestFont:
    """Tests for the ``Font`` Pydantic model."""

    class TestWeight:
        """Tests for the ``Font.weight`` computed field."""

        def test_bold_detected_case_insensitive(self) -> None:
            """Font name containing ``"bold"`` (any case) returns ``BOLD``."""
            font = Font(font="ArialBold", size=12.0, font_dictionary=MagicMock(spec=IndirectObject))
            assert font.weight == FontWeight.BOLD

        def test_light_detected(self) -> None:
            """Font name containing ``"light"`` returns ``LIGHT``."""
            font = Font(font="ArialLight", size=10.0, font_dictionary=MagicMock(spec=IndirectObject))
            assert font.weight == FontWeight.LIGHT

        def test_regular_is_default(self) -> None:
            """Font name not containing ``"bold"`` or ``"light"`` returns
            ``REGULAR``."""
            font = Font(font="Arial", size=10.0, font_dictionary=MagicMock(spec=IndirectObject))
            assert font.weight == FontWeight.REGULAR

        def test_bold_takes_precedence_over_light(self) -> None:
            """When the font name contains both ``"bold"`` and ``"light"``, ``BOLD`` is
            returned first."""
            font = Font(font="ArialBoldLight", size=10.0, font_dictionary=MagicMock(spec=IndirectObject))
            assert font.weight == FontWeight.BOLD

    class TestRaiseOverlappingGlyphs:
        """Tests for ``Font.raise_overlapping_glyphs``."""

        def test_no_overlap_does_not_raise(self) -> None:
            """A list of characters that does not include delimiter glyphs passes
            silently."""
            Font.raise_overlapping_glyphs(["A", "B", "C"])

        def test_overlapping_glyph_raises_value_error(self) -> None:
            """A character matching a ``DelimiterGlyph`` raises ``ValueError``."""
            with pytest.raises(ValueError, match="Delimiter glyphs"):
                Font.raise_overlapping_glyphs([DelimiterGlyph.RETURN])

        def test_end_object_glyph_raises(self) -> None:
            """The ``END_OBJECT`` delimiter raises ``ValueError``."""
            with pytest.raises(ValueError):
                Font.raise_overlapping_glyphs([DelimiterGlyph.END_OBJECT])

        def test_empty_list_does_not_raise(self) -> None:
            """An empty character list passes without error."""
            Font.raise_overlapping_glyphs([])

        def test_error_message_includes_glyph(self) -> None:
            """The error message names the offending delimiter glyph."""
            with pytest.raises(ValueError, match=DelimiterGlyph.ATTRIBUTES_OPEN):
                Font.raise_overlapping_glyphs([DelimiterGlyph.ATTRIBUTES_OPEN])

    class TestCharacters:
        """Tests for the ``Font.characters`` computed field."""

        def test_returns_ord_keyed_dict(self) -> None:
            """Character codes are converted to integer ordinals in the returned
            mapping."""
            mock_dict: MagicMock = MagicMock(spec=IndirectObject)
            font = Font(font="Arial", size=12.0, font_dictionary=mock_dict)

            raw: dict = {chr(65): "A", chr(66): "B", chr(67): "C", -1: "reserved"}

            with patch("pa_record_retriever.pypdf.models._parse_to_unicode", return_value=(raw, {})):
                characters = font.characters

            assert 65 in characters
            assert characters[65] == "A"

        def test_last_entry_removed(self) -> None:
            """The ``-1`` sentinel key inserted by ``pypdf`` is removed before the
            mapping is returned."""
            mock_dict: MagicMock = MagicMock(spec=IndirectObject)
            font = Font(font="Arial", size=12.0, font_dictionary=mock_dict)

            raw: dict = {chr(65): "A", chr(66): "B", -1: "reserved"}

            with patch("pa_record_retriever.pypdf.models._parse_to_unicode", return_value=(raw, {})):
                characters = font.characters

            assert len(characters) == 2
            assert 65 in characters
            assert 66 in characters

        def test_overlapping_glyph_raises(self) -> None:
            """A CMap containing a delimiter glyph raises ``ValueError``."""
            mock_dict: MagicMock = MagicMock(spec=IndirectObject)
            font = Font(font="Arial", size=12.0, font_dictionary=mock_dict)

            raw: dict = {chr(65): DelimiterGlyph.RETURN, -1: "reserved"}

            with (
                patch("pa_record_retriever.pypdf.models._parse_to_unicode", return_value=(raw, {})),
                pytest.raises(ValueError, match="Delimiter glyphs"),
            ):
                _ = font.characters

    class TestWidths:
        """Tests for the ``Font.widths`` computed field."""

        def test_returns_mapping_of_code_to_width(self) -> None:
            """Width entries are correctly mapped from the font dictionary for known
            character codes."""
            font = Font.model_construct(font="Arial", size=12.0, font_dictionary={})

            font.__dict__["characters"] = {65: "A", 66: "B"}

            mock_type1: MagicMock = MagicMock()
            mock_type1.first_character = 65
            mock_type1.last_character = 66
            mock_type1.widths = [250, 300]

            with patch("pa_record_retriever.pypdf.models.Type1FontDictionary", return_value=mock_type1):
                widths = font.widths

            assert widths == {65: 250, 66: 300}

        def test_skips_codes_not_in_characters(self) -> None:
            """Character codes absent from the ``characters`` mapping are excluded from
            widths."""
            font = Font.model_construct(font="Arial", size=12.0, font_dictionary={})

            font.__dict__["characters"] = {65: "A"}

            mock_type1: MagicMock = MagicMock()
            mock_type1.first_character = 65
            mock_type1.last_character = 66
            mock_type1.widths = [250, 300]

            with patch("pa_record_retriever.pypdf.models.Type1FontDictionary", return_value=mock_type1):
                widths = font.widths

            assert 66 not in widths
            assert widths[65] == 250

    class TestFromOperands:
        """Tests for ``Font.from_operands``."""

        def test_raises_on_wrong_operand_count(self) -> None:
            """Passing fewer or more than two operands raises ``ValueError``."""
            mock_page: MagicMock = MagicMock()
            with pytest.raises(ValueError, match="exactly two elements"):
                Font.from_operands(operands=["/F1"], page=mock_page)

        def test_returns_font_instance(self) -> None:
            """Valid operands and page resources produce a ``Font`` instance."""
            fake_dict = _FakeFontDict("ArialMT")

            mock_page: MagicMock = MagicMock()
            mock_page.get.return_value = {"/Font": {"/F1": fake_dict}}

            font = Font.from_operands(operands=["/F1", 12.0], page=mock_page)

            assert isinstance(font, Font)
            assert font.size == 12.0

        def test_font_name_taken_from_base_font_entry(self) -> None:
            """The ``font`` field is populated from the ``BASE_FONT`` entry of the font
            dictionary."""
            fake_dict = _FakeFontDict("TimesNewRoman")

            mock_page: MagicMock = MagicMock()
            mock_page.get.return_value = {"/Font": {"/F2": fake_dict}}

            font = Font.from_operands(operands=["/F2", 10.0], page=mock_page)

            assert font.font == "TimesNewRoman"

    class TestDecode:
        """Tests for ``Font.decode``."""

        def test_decodes_byte_string_to_content_and_width(self) -> None:
            """Each byte is decoded to its character and its width is summed."""
            mock_dict: MagicMock = MagicMock(spec=IndirectObject)
            font = Font(font="Arial", size=12.0, font_dictionary=mock_dict)

            font.__dict__["characters"] = {65: "A", 66: "B"}
            font.__dict__["widths"] = {65: 100, 66: 200}

            content, width = font.decode(b"AB")

            assert content == "AB"
            assert width == 300

        def test_empty_byte_string_returns_empty_content_zero_width(self) -> None:
            """An empty byte string produces an empty string and zero total width."""
            mock_dict: MagicMock = MagicMock(spec=IndirectObject)
            font = Font(font="Arial", size=12.0, font_dictionary=mock_dict)

            font.__dict__["characters"] = {}
            font.__dict__["widths"] = {}

            content, width = font.decode(b"")

            assert content == ""
            assert width == 0


class TestBoundingBox:
    """Tests for the ``BoundingBox`` Pydantic model."""

    class TestCeiling:
        """Tests for the ``BoundingBox.ceiling`` field validator."""

        def test_float_is_rounded_up(self) -> None:
            """A float coordinate is rounded up to the nearest integer."""
            box = BoundingBox(x_min=1.2)
            assert box.x_min == 2

        def test_integer_is_unchanged(self) -> None:
            """An integer coordinate is passed through without modification."""
            box = BoundingBox(x_min=5)
            assert box.x_min == 5

        def test_negative_float_is_rounded_up(self) -> None:
            """A negative float is rounded toward zero (ceiling behaviour)."""
            box = BoundingBox(y_min=-1.9)
            assert box.y_min == -1

        def test_width_float_rounded_up(self) -> None:
            """A float ``width`` is rounded up before storage."""
            box = BoundingBox(width=3.1)
            assert box.width == 4

    class TestXMax:
        """Tests for the ``BoundingBox.x_max`` property."""

        def test_equals_x_min_plus_width(self) -> None:
            """``x_max`` is the sum of ``x_min`` and ``width``."""
            box = BoundingBox(x_min=10, width=50)
            assert box.x_max == 60

        def test_zero_width_equals_x_min(self) -> None:
            """When ``width`` is zero, ``x_max`` equals ``x_min``."""
            box = BoundingBox(x_min=25)
            assert box.x_max == 25

    class TestYMax:
        """Tests for the ``BoundingBox.y_max`` property."""

        def test_equals_y_min_plus_height(self) -> None:
            """``y_max`` is the sum of ``y_min`` and ``height``."""
            box = BoundingBox(y_min=5, height=20)
            assert box.y_max == 25

    class TestXCenter:
        """Tests for the ``BoundingBox.x_center`` property."""

        def test_equals_ceiling_of_x_min_plus_half_width(self) -> None:
            """``x_center`` is the ceiling of ``x_min + width / 2``."""
            box = BoundingBox(x_min=10, width=5)
            assert box.x_center == 13

        def test_even_width_center_is_exact(self) -> None:
            """An even ``width`` produces an exact (non-rounded) center."""
            box = BoundingBox(x_min=0, width=10)
            assert box.x_center == 5

    class TestYCenter:
        """Tests for the ``BoundingBox.y_center`` property."""

        def test_equals_ceiling_of_y_min_plus_half_height(self) -> None:
            """``y_center`` is the ceiling of ``y_min + height / 2``."""
            box = BoundingBox(y_min=0, height=7)
            assert box.y_center == 4


class TestTextObject:
    """Tests for the ``TextObject`` Pydantic model."""

    class TestSerialize:
        """Tests for ``TextObject.serialize``."""

        def test_raises_when_font_is_none(self) -> None:
            """``serialize`` raises ``ValueError`` when ``font`` has not been set."""
            obj = TextObject(content="hello", bounding_box=BoundingBox())
            with pytest.raises(ValueError, match="Font and bounding box must be set"):
                obj.serialize()

        def test_raises_when_bounding_box_is_none(self) -> None:
            """``serialize`` raises ``ValueError`` when ``bounding_box`` has not been
            set."""
            mock_font: MagicMock = MagicMock(spec=Font)
            obj = TextObject(content="hello", font=mock_font)
            with pytest.raises(ValueError, match="Font and bounding box must be set"):
                obj.serialize()

        def test_output_ends_with_end_object_delimiter(self) -> None:
            """The serialized string ends with the ``END_OBJECT`` delimiter."""
            mock_font: MagicMock = MagicMock(spec=Font)
            mock_font.weight = FontWeight.REGULAR

            obj = TextObject(content="hello", font=mock_font, bounding_box=BoundingBox(x_min=10, width=20))
            result = obj.serialize()

            assert result.endswith(DelimiterGlyph.END_OBJECT)

        def test_output_contains_attributes_delimiters(self) -> None:
            """The serialized string contains opening and closing attribute
            delimiters."""
            mock_font: MagicMock = MagicMock(spec=Font)
            mock_font.weight = FontWeight.BOLD

            obj = TextObject(content="text", font=mock_font, bounding_box=BoundingBox(x_min=5, width=10))
            result = obj.serialize()

            assert DelimiterGlyph.ATTRIBUTES_OPEN in result
            assert DelimiterGlyph.ATTRIBUTES_CLOSE in result

        def test_output_starts_with_content(self) -> None:
            """The serialized string begins with the text object's content."""
            mock_font: MagicMock = MagicMock(spec=Font)
            mock_font.weight = FontWeight.LIGHT

            obj = TextObject(content="word", font=mock_font, bounding_box=BoundingBox(x_min=0, width=30))
            result = obj.serialize()

            assert result.startswith("word")

        def test_coordinates_are_zero_padded_to_three_digits(self) -> None:
            """Coordinate values in the attribute block are left-padded with zeros to
            three digits."""
            mock_font: MagicMock = MagicMock(spec=Font)
            mock_font.weight = FontWeight.REGULAR

            obj = TextObject(content="x", font=mock_font, bounding_box=BoundingBox(x_min=5, width=4))
            result = obj.serialize()

            assert "005" in result

        def test_font_weight_included_in_attributes(self) -> None:
            """The font weight string appears in the attribute block."""
            mock_font: MagicMock = MagicMock(spec=Font)
            mock_font.weight = FontWeight.BOLD

            obj = TextObject(content="z", font=mock_font, bounding_box=BoundingBox(x_min=0, width=0))
            result = obj.serialize()

            assert FontWeight.BOLD in result
