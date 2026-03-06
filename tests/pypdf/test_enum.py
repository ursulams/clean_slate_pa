from pa_record_retriever.pypdf.enum import (
    BytesEnumMeta,
    DelimiterGlyph,
    Entry,
    FontEntry,
    FontWeight,
    Operator,
)


class TestEntry:
    """Tests for the ``Entry`` StrEnum."""

    def test_resources_value(self) -> None:
        """``RESOURCES`` has the expected PDF key string."""
        assert Entry.RESOURCES == "/Resources"

    def test_font_value(self) -> None:
        """``FONT`` has the expected PDF key string."""
        assert Entry.FONT == "/Font"

    def test_is_str(self) -> None:
        """Members behave as plain strings."""
        assert isinstance(Entry.RESOURCES, str)


class TestFontEntry:
    """Tests for the ``FontEntry`` StrEnum."""

    def test_type_value(self) -> None:
        """``TYPE`` matches the PDF font dictionary key."""
        assert FontEntry.TYPE == "/Type"

    def test_subtype_value(self) -> None:
        """``SUBTYPE`` matches the PDF font dictionary key."""
        assert FontEntry.SUBTYPE == "/Subtype"

    def test_base_font_value(self) -> None:
        """``BASE_FONT`` matches the PDF font dictionary key."""
        assert FontEntry.BASE_FONT == "/BaseFont"

    def test_first_character_value(self) -> None:
        """``FIRST_CHARACTER`` matches the PDF font dictionary key."""
        assert FontEntry.FIRST_CHARACTER == "/FirstChar"

    def test_last_character_value(self) -> None:
        """``LAST_CHARACTER`` matches the PDF font dictionary key."""
        assert FontEntry.LAST_CHARACTER == "/LastChar"

    def test_widths_value(self) -> None:
        """``WIDTHS`` matches the PDF font dictionary key."""
        assert FontEntry.WIDTHS == "/Widths"

    def test_font_descriptor_value(self) -> None:
        """``FONT_DESCRIPTOR`` matches the PDF font dictionary key."""
        assert FontEntry.FONT_DESCRIPTOR == "/FontDescriptor"

    def test_encoding_value(self) -> None:
        """``ENCODING`` matches the PDF font dictionary key."""
        assert FontEntry.ENCODING == "/Encoding"

    def test_to_unicode_value(self) -> None:
        """``TO_UNICODE`` matches the PDF font dictionary key."""
        assert FontEntry.TO_UNICODE == "/ToUnicode"


class TestFontWeight:
    """Tests for the ``FontWeight`` StrEnum."""

    def test_light_value(self) -> None:
        """``LIGHT`` has the expected lowercase string value."""
        assert FontWeight.LIGHT == "light"

    def test_regular_value(self) -> None:
        """``REGULAR`` has the expected lowercase string value."""
        assert FontWeight.REGULAR == "regular"

    def test_bold_value(self) -> None:
        """``BOLD`` has the expected lowercase string value."""
        assert FontWeight.BOLD == "bold"

    def test_members_are_strings(self) -> None:
        """All members are instances of ``str``."""
        for member in FontWeight:
            assert isinstance(member, str)


class TestDelimiterGlyph:
    """Tests for the ``DelimiterGlyph`` StrEnum."""

    def test_end_object_is_newline(self) -> None:
        """``END_OBJECT`` is a newline character."""
        assert DelimiterGlyph.END_OBJECT == "\n"

    def test_return_value(self) -> None:
        """``RETURN`` is the return arrow glyph."""
        assert DelimiterGlyph.RETURN == "↩"

    def test_attributes_open_value(self) -> None:
        """``ATTRIBUTES_OPEN`` is the opening double angle bracket."""
        assert DelimiterGlyph.ATTRIBUTES_OPEN == "《"

    def test_attributes_close_value(self) -> None:
        """``ATTRIBUTES_CLOSE`` is the closing double angle bracket."""
        assert DelimiterGlyph.ATTRIBUTES_CLOSE == "》"

    def test_members_are_strings(self) -> None:
        """All members are instances of ``str``."""
        for member in DelimiterGlyph:
            assert isinstance(member, str)


class TestBytesEnumMeta:
    """Tests for the ``BytesEnumMeta`` metaclass."""

    class TestIter:
        """Tests for ``BytesEnumMeta.__iter__``."""

        def test_iterates_raw_byte_values(self) -> None:
            """Iterating over an enum class yields raw byte values, not enum members."""
            values = list(Operator)
            assert all(isinstance(v, bytes) for v in values)

        def test_yields_all_member_values(self) -> None:
            """The iterator yields one value per enum member."""
            assert len(list(Operator)) == len(Operator.__members__)

        def test_end_text_object_in_iteration(self) -> None:
            """``END_TEXT_OBJECT``'s byte value appears in the iteration output."""
            assert b"ET" in list(Operator)

    class TestContains:
        """Tests for ``BytesEnumMeta.__contains__``."""

        def test_known_bytes_value_is_contained(self) -> None:
            """A bytes value matching a member returns ``True``."""
            assert b"ET" in Operator

        def test_unknown_bytes_value_not_contained(self) -> None:
            """A bytes value not matching any member returns ``False``."""
            assert b"XX" not in Operator

        def test_non_bytes_value_not_contained(self) -> None:
            """A non-``bytes`` value always returns ``False``."""
            assert "ET" not in Operator

        def test_integer_not_contained(self) -> None:
            """An integer value always returns ``False``."""
            assert 42 not in Operator

        def test_none_not_contained(self) -> None:
            """``None`` is not contained in a ``BytesEnum``."""
            assert None not in Operator


class TestBytesEnum:
    """Tests for the ``BytesEnum`` base class."""

    def test_is_bytes_subclass(self) -> None:
        """``BytesEnum`` members are instances of ``bytes``."""
        assert isinstance(Operator.END_TEXT_OBJECT, bytes)

    def test_uses_bytes_enum_meta(self) -> None:
        """``BytesEnum`` uses ``BytesEnumMeta`` as its metaclass."""
        assert type(Operator) is BytesEnumMeta


class TestOperator:
    """Tests for the ``Operator`` BytesEnum."""

    def test_end_text_object_value(self) -> None:
        """``END_TEXT_OBJECT`` matches the PDF ET operator."""
        assert Operator.END_TEXT_OBJECT == b"ET"

    def test_save_graphics_state_value(self) -> None:
        """``SAVE_GRAPHICS_STATE`` matches the PDF q operator."""
        assert Operator.SAVE_GRAPHICS_STATE == b"q"

    def test_restore_graphics_state_value(self) -> None:
        """``RESTORE_GRAPHICS_STATE`` matches the PDF Q operator."""
        assert Operator.RESTORE_GRAPHICS_STATE == b"Q"

    def test_move_text_position_value(self) -> None:
        """``MOVE_TEXT_POSITION`` matches the PDF Td operator."""
        assert Operator.MOVE_TEXT_POSITION == b"Td"

    def test_set_font_value(self) -> None:
        """``SET_FONT`` matches the PDF Tf operator."""
        assert Operator.SET_FONT == b"Tf"

    def test_show_text_string_value(self) -> None:
        """``SHOW_TEXT_STRING`` matches the PDF Tj operator."""
        assert Operator.SHOW_TEXT_STRING == b"Tj"

    def test_show_text_strings_value(self) -> None:
        """``SHOW_TEXT_STRINGS`` matches the PDF TJ operator."""
        assert Operator.SHOW_TEXT_STRINGS == b"TJ"

    def test_all_members_are_bytes(self) -> None:
        """All ``Operator`` members are instances of ``bytes``."""
        for value in list(Operator):
            assert isinstance(value, bytes)
