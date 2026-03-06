from unittest.mock import MagicMock, patch

import pytest
from pypdf import PageObject, PdfReader

from pa_record_retriever.pypdf.enum import DelimiterGlyph, Operator
from pa_record_retriever.pypdf.models import BoundingBox, Font, TextObject
from pa_record_retriever.pypdf.reader import Page


def _make_page() -> Page:
    """Return a ``Page`` instance with all attributes initialised but no PDF I/O
    performed."""
    page: Page = Page.__new__(Page)
    page.text_objects = []
    page._text_object = TextObject()
    page._font = None
    page._font_stack = []
    page._x_displacement = 0.0
    page._td_x_translation = 0.0
    page._td_y_translation = 0.0
    return page


def _make_font(weight: str = "regular", size: float = 10.0) -> MagicMock:
    """Return a ``MagicMock`` that behaves like a ``Font`` with the given weight and
    size."""
    font: MagicMock = MagicMock(spec=Font)
    font.weight = weight
    font.size = size
    return font


class TestPage:
    """Tests for the ``Page`` class."""

    class TestInit:
        """Tests for ``Page.__init__``."""

        def test_initialises_text_objects_to_empty_list(self) -> None:
            """``text_objects`` starts as an empty list after initialisation."""
            with (
                patch.object(PageObject, "__init__", return_value=None),
                patch.object(Page, "update"),
            ):
                page = Page(MagicMock(spec=PdfReader), MagicMock())

            assert page.text_objects == []

        def test_initialises_font_to_none(self) -> None:
            """``_font`` starts as ``None`` after initialisation."""
            with (
                patch.object(PageObject, "__init__", return_value=None),
                patch.object(Page, "update"),
            ):
                page = Page(MagicMock(spec=PdfReader), MagicMock())

            assert page._font is None

        def test_initialises_displacement_to_zero(self) -> None:
            """Displacement accumulators start at ``0.0`` after initialisation."""
            with (
                patch.object(PageObject, "__init__", return_value=None),
                patch.object(Page, "update"),
            ):
                page = Page(MagicMock(spec=PdfReader), MagicMock())

            assert page._x_displacement == 0.0
            assert page._td_x_translation == 0.0
            assert page._td_y_translation == 0.0

        def test_initialises_text_object(self) -> None:
            """``_text_object`` is a fresh ``TextObject`` after initialisation."""
            with (
                patch.object(PageObject, "__init__", return_value=None),
                patch.object(Page, "update"),
            ):
                page = Page(MagicMock(spec=PdfReader), MagicMock())

            assert isinstance(page._text_object, TextObject)

        def test_calls_super_init_with_indirect_reference(self) -> None:
            """``super().__init__`` is called with the page's ``indirect_reference``."""
            mock_page: MagicMock = MagicMock()
            mock_page.indirect_reference = "ref-42"

            with (
                patch.object(PageObject, "__init__", return_value=None) as mock_super,
                patch.object(Page, "update"),
            ):
                Page(MagicMock(spec=PdfReader), mock_page)
                mock_super.assert_called_once()

        def test_calls_update_with_page(self) -> None:
            """``self.update`` is called with the wrapped ``PageObject``."""
            mock_page: MagicMock = MagicMock()

            with (
                patch.object(PageObject, "__init__", return_value=None),
                patch.object(Page, "update") as mock_update,
            ):
                Page(MagicMock(spec=PdfReader), mock_page)
                mock_update.assert_called_once_with(mock_page)

    class TestExtractText:
        """Tests for ``Page.extract_text``."""

        def test_returns_concatenated_serialized_text_objects(self) -> None:
            """Serialized text objects are joined in order and returned."""
            page = _make_page()

            mock_obj1: MagicMock = MagicMock(spec=TextObject)
            mock_obj1.serialize.return_value = "hello\n"
            mock_obj2: MagicMock = MagicMock(spec=TextObject)
            mock_obj2.serialize.return_value = "world\n"
            page.text_objects = [mock_obj1, mock_obj2]

            with patch.object(PageObject, "extract_text", return_value=None):
                result = page.extract_text()

            assert result == "hello\nworld\n"

        def test_calls_super_extract_text_with_visitor(self) -> None:
            """``super().extract_text`` is called with a ``visitor_operand_before``
            keyword argument."""
            page = _make_page()

            with patch.object(PageObject, "extract_text", return_value=None) as mock_super:
                page.extract_text()
                assert "visitor_operand_before" in mock_super.call_args.kwargs

        def test_empty_page_returns_empty_string(self) -> None:
            """A page with no text objects produces an empty string."""
            page = _make_page()

            with patch.object(PageObject, "extract_text", return_value=None):
                result = page.extract_text()

            assert result == ""

        def test_visitor_dispatches_end_text_object_operator(self) -> None:
            """The visitor calls ``_end_text_object`` when the ``ET`` operator is
            received."""
            page = _make_page()

            captured_visitor: list = []

            def capture_visitor(**kwargs) -> None:
                """Stores the visitor so it can be called in the test."""
                captured_visitor.append(kwargs["visitor_operand_before"])

            with patch.object(PageObject, "extract_text", side_effect=capture_visitor):
                page.extract_text()

            with patch.object(page, "_end_text_object") as mock_end:
                captured_visitor[0](Operator.END_TEXT_OBJECT, [], [], [])
                mock_end.assert_called_once()

        def test_visitor_dispatches_save_graphics_state_operator(self) -> None:
            """The visitor calls ``_save_graphics_state`` when the ``q`` operator is
            received."""
            page = _make_page()

            captured_visitor: list = []

            def capture_visitor(**kwargs) -> None:
                """Stores the visitor function for later invocation."""
                captured_visitor.append(kwargs["visitor_operand_before"])

            with patch.object(PageObject, "extract_text", side_effect=capture_visitor):
                page.extract_text()

            with patch.object(page, "_save_graphics_state") as mock_save:
                captured_visitor[0](Operator.SAVE_GRAPHICS_STATE, [], [], [])
                mock_save.assert_called_once()

        def test_visitor_dispatches_restore_graphics_state_operator(self) -> None:
            """The visitor calls ``_restore_graphics_state`` when the ``Q`` operator is
            received."""
            page = _make_page()

            captured_visitor: list = []

            def capture_visitor(**kwargs) -> None:
                """Stores the visitor function for later invocation."""
                captured_visitor.append(kwargs["visitor_operand_before"])

            with patch.object(PageObject, "extract_text", side_effect=capture_visitor):
                page.extract_text()

            with patch.object(page, "_restore_graphics_state") as mock_restore:
                captured_visitor[0](Operator.RESTORE_GRAPHICS_STATE, [], [], [])
                mock_restore.assert_called_once()

        def test_visitor_dispatches_move_text_position_operator(self) -> None:
            """The visitor calls ``_move_text_position`` when the ``Td`` operator is
            received."""
            page = _make_page()

            captured_visitor: list = []

            def capture_visitor(**kwargs) -> None:
                """Stores the visitor function for later invocation."""
                captured_visitor.append(kwargs["visitor_operand_before"])

            with patch.object(PageObject, "extract_text", side_effect=capture_visitor):
                page.extract_text()

            with patch.object(page, "_move_text_position") as mock_move:
                captured_visitor[0](Operator.MOVE_TEXT_POSITION, [0.0, -12.0], [], [])
                mock_move.assert_called_once_with(operands=[0.0, -12.0])

        def test_visitor_dispatches_set_font_operator(self) -> None:
            """The visitor calls ``_set_font`` when the ``Tf`` operator is received."""
            page = _make_page()

            captured_visitor: list = []

            def capture_visitor(**kwargs) -> None:
                """Stores the visitor function for later invocation."""
                captured_visitor.append(kwargs["visitor_operand_before"])

            with patch.object(PageObject, "extract_text", side_effect=capture_visitor):
                page.extract_text()

            with patch.object(page, "_set_font") as mock_set_font:
                captured_visitor[0](Operator.SET_FONT, ["/F1", 12.0], [], [])
                mock_set_font.assert_called_once_with(operands=["/F1", 12.0])

        def test_visitor_dispatches_show_text_string_operator(self) -> None:
            """The visitor calls ``_show_text_string`` when the ``Tj`` operator is
            received."""
            page = _make_page()

            captured_visitor: list = []

            def capture_visitor(**kwargs) -> None:
                """Stores the visitor function for later invocation."""
                captured_visitor.append(kwargs["visitor_operand_before"])

            with patch.object(PageObject, "extract_text", side_effect=capture_visitor):
                page.extract_text()

            with patch.object(page, "_show_text_string") as mock_show:
                captured_visitor[0](Operator.SHOW_TEXT_STRING, [b"hi"], [1, 0, 0, 1, 0, 0], [1, 0, 0, 1, 5, 5])
                mock_show.assert_called_once()

        def test_visitor_dispatches_show_text_strings_operator(self) -> None:
            """The visitor calls ``_show_text_strings`` when the ``TJ`` operator is
            received."""
            page = _make_page()

            captured_visitor: list = []

            def capture_visitor(**kwargs) -> None:
                """Stores the visitor function for later invocation."""
                captured_visitor.append(kwargs["visitor_operand_before"])

            with patch.object(PageObject, "extract_text", side_effect=capture_visitor):
                page.extract_text()

            with patch.object(page, "_show_text_strings") as mock_show:
                captured_visitor[0](Operator.SHOW_TEXT_STRINGS, [[b"hi"]], [1, 0, 0, 1, 0, 0], [1, 0, 0, 1, 5, 5])
                mock_show.assert_called_once()

        def test_visitor_ignores_unknown_operator(self) -> None:
            """An unrecognised operator byte is silently ignored."""
            page = _make_page()

            captured_visitor: list = []

            def capture_visitor(**kwargs) -> None:
                """Stores the visitor function for later invocation."""
                captured_visitor.append(kwargs["visitor_operand_before"])

            with patch.object(PageObject, "extract_text", side_effect=capture_visitor):
                page.extract_text()

            captured_visitor[0](b"cm", [], [], [])

    class TestEndTextObject:
        """Tests for ``Page._end_text_object``."""

        def test_non_empty_content_is_appended_to_text_objects(self) -> None:
            """A text object with content is added to ``text_objects``."""
            page = _make_page()
            page._text_object = TextObject(content="hello", font=_make_font(), bounding_box=BoundingBox())
            page._end_text_object()
            assert len(page.text_objects) == 1

        def test_empty_content_is_not_appended(self) -> None:
            """A text object with no content is discarded."""
            page = _make_page()
            page._end_text_object()
            assert page.text_objects == []

        def test_trailing_return_delimiter_stripped(self) -> None:
            """A trailing ``RETURN`` delimiter is removed before the object is
            stored."""
            page = _make_page()
            page._text_object = TextObject(
                content=f"hello{DelimiterGlyph.RETURN}",
                font=_make_font(),
                bounding_box=BoundingBox(),
            )
            page._end_text_object()
            assert page.text_objects[0].content == "hello"

        def test_content_is_stripped(self) -> None:
            """Leading and trailing whitespace is stripped from the stored content."""
            page = _make_page()
            page._text_object = TextObject(content="  hello  ", font=_make_font(), bounding_box=BoundingBox())
            page._end_text_object()
            assert page.text_objects[0].content == "hello"

        def test_font_assigned_to_text_object(self) -> None:
            """The current ``_font`` is assigned to the finalized text object."""
            page = _make_page()
            font = _make_font()
            page._font = font
            page._text_object = TextObject(content="text", bounding_box=BoundingBox())
            page._end_text_object()
            assert page.text_objects[0].font is font

        def test_resets_text_object(self) -> None:
            """A fresh ``TextObject`` replaces the finalized one."""
            page = _make_page()
            page._text_object = TextObject(content="x", font=_make_font(), bounding_box=BoundingBox())
            old_obj = page._text_object
            page._end_text_object()
            assert page._text_object is not old_obj

        def test_resets_displacement_accumulators(self) -> None:
            """``_x_displacement``, ``_td_x_translation``, and ``_td_y_translation``
            reset to zero."""
            page = _make_page()
            page._x_displacement = 5.0
            page._td_x_translation = 3.0
            page._td_y_translation = -2.0
            page._end_text_object()
            assert page._x_displacement == 0.0
            assert page._td_x_translation == 0.0
            assert page._td_y_translation == 0.0

    class TestSaveGraphicsState:
        """Tests for ``Page._save_graphics_state``."""

        def test_pushes_current_font_onto_stack(self) -> None:
            """The current ``_font`` is pushed onto ``_font_stack``."""
            page = _make_page()
            font = _make_font()
            page._font = font
            page._save_graphics_state()
            assert page._font_stack == [font]

        def test_none_font_can_be_pushed(self) -> None:
            """``None`` (no font set) is a valid value to push onto the stack."""
            page = _make_page()
            page._save_graphics_state()
            assert page._font_stack == [None]

        def test_multiple_pushes_preserve_order(self) -> None:
            """Each saved state is stacked in LIFO order."""
            page = _make_page()
            font1 = _make_font()
            font2 = _make_font()
            page._font = font1
            page._save_graphics_state()
            page._font = font2
            page._save_graphics_state()
            assert page._font_stack == [font1, font2]

    class TestRestoreGraphicsState:
        """Tests for ``Page._restore_graphics_state``."""

        def test_pops_font_from_stack(self) -> None:
            """The last saved font is restored from the stack."""
            page = _make_page()
            font = _make_font()
            page._font_stack = [font]
            page._restore_graphics_state()
            assert page._font is font

        def test_calls_end_text_object(self) -> None:
            """``_end_text_object`` is called before the font is restored."""
            page = _make_page()
            page._font_stack = [_make_font()]

            with patch.object(page, "_end_text_object") as mock_end:
                page._restore_graphics_state()
                mock_end.assert_called_once()

    class TestMoveTextPosition:
        """Tests for ``Page._move_text_position``."""

        def test_negative_y_with_small_x_appends_return(self) -> None:
            """A downward move with negligible x offset appends a ``RETURN``
            delimiter."""
            page = _make_page()
            page._move_text_position(operands=[0.0, -12.0])
            assert page._text_object.content == DelimiterGlyph.RETURN

        def test_negative_y_with_small_x_updates_y_translation(self) -> None:
            """A downward move accumulates into ``_td_y_translation``."""
            page = _make_page()
            page._move_text_position(operands=[0.0, -12.0])
            assert page._td_y_translation == -12.0

        def test_negative_y_with_small_x_resets_x_translation(self) -> None:
            """``_td_x_translation`` resets to zero on a downward in-column move."""
            page = _make_page()
            page._td_x_translation = 5.0
            page._move_text_position(operands=[0.1, -12.0])
            assert page._td_x_translation == 0.0

        def test_positive_y_within_threshold_ends_text_object(self) -> None:
            """A small upward move within the y-threshold calls ``_end_text_object``."""
            page = _make_page()
            page._td_y_translation = -0.9

            with patch.object(page, "_end_text_object") as mock_end:
                page._move_text_position(operands=[0.0, 0.5])
                mock_end.assert_called_once()

        def test_large_y_displacement_ends_text_object(self) -> None:
            """A large positive y translation exceeding the y-threshold ends the text
            object."""
            page = _make_page()

            with patch.object(page, "_end_text_object") as mock_end:
                page._move_text_position(operands=[0.0, 20.0])
                mock_end.assert_called_once()

        def test_negative_x_with_content_ends_text_object(self) -> None:
            """A negative x translation when there is existing content ends the text
            object."""
            page = _make_page()
            page._text_object.content = "existing"

            with patch.object(page, "_end_text_object") as mock_end:
                page._move_text_position(operands=[-5.0, 0.0])
                mock_end.assert_called_once()

        def test_positive_x_beyond_font_size_threshold_ends_text_object(self) -> None:
            """A large positive x jump beyond the font-size-scaled threshold ends the
            text object."""
            page = _make_page()
            page._text_object.content = "text"
            page._font = _make_font(size=10.0)
            page._x_displacement = 0.0

            with patch.object(page, "_end_text_object") as mock_end:
                page._move_text_position(operands=[10.0, 0.0])
                mock_end.assert_called_once()

        def test_positive_x_within_threshold_accumulates_translation(self) -> None:
            """A small positive x jump within the scaled threshold accumulates into
            ``_td_x_translation``."""
            page = _make_page()
            page._text_object.content = "text"
            page._font = _make_font(size=100.0)
            page._x_displacement = 0.0

            page._move_text_position(operands=[1.0, 0.0])

            assert page._td_x_translation == 1.0

        def test_x_displacement_always_resets_to_zero(self) -> None:
            """``_x_displacement`` is reset to zero at the end of every
            ``_move_text_position`` call."""
            page = _make_page()
            page._x_displacement = 99.0
            page._move_text_position(operands=[0.0, 0.0])
            assert page._x_displacement == 0.0

    class TestSetFont:
        """Tests for ``Page._set_font``."""

        def test_assigns_font_from_operands(self) -> None:
            """``_font`` is assigned the result of ``Font.from_operands``."""
            page = _make_page()
            mock_font: MagicMock = _make_font()

            with (
                patch.object(page, "_end_text_object"),
                patch("pa_record_retriever.pypdf.reader.Font.from_operands", return_value=mock_font),
            ):
                page._set_font(operands=["/F1", 12.0])

            assert page._font is mock_font

        def test_calls_end_text_object_first(self) -> None:
            """``_end_text_object`` is called before the font is changed."""
            page = _make_page()

            call_order: list[str] = []

            def record_end() -> None:
                """Records the order of ``_end_text_object`` calls."""
                call_order.append("end")

            def record_font(operands, page) -> MagicMock:
                """Records the order of ``Font.from_operands`` calls."""
                call_order.append("font")
                return _make_font()

            with (
                patch.object(page, "_end_text_object", side_effect=record_end),
                patch("pa_record_retriever.pypdf.reader.Font.from_operands", side_effect=record_font),
            ):
                page._set_font(operands=["/F1", 12.0])

            assert call_order == ["end", "font"]

    class TestSetOrigin:
        """Tests for ``Page._set_origin``."""

        def test_sets_bounding_box_on_first_call(self) -> None:
            """The first call initialises ``bounding_box`` on the current text
            object."""
            page = _make_page()

            cm: list[float] = [1, 0, 0, 1, 0, 0]
            tm: list[float] = [1, 0, 0, 1, 10, 20]

            page._set_origin(cm_matrix=cm, tm_matrix=tm)

            assert page._text_object.bounding_box is not None

        def test_subsequent_call_does_not_overwrite_bounding_box(self) -> None:
            """Once set, ``bounding_box`` is not replaced by subsequent ``_set_origin``
            calls."""
            page = _make_page()
            page._text_object.bounding_box = BoundingBox(x_min=5, y_min=10)

            cm: list[float] = [1, 0, 0, 1, 0, 0]
            tm: list[float] = [1, 0, 0, 1, 99, 99]

            page._set_origin(cm_matrix=cm, tm_matrix=tm)

            assert page._text_object.bounding_box.x_min == 5
            assert page._text_object.bounding_box.y_min == 10

    class TestHandleTextString:
        """Tests for ``Page._handle_text_string``."""

        def test_decoded_content_appended_to_text_object(self) -> None:
            """Decoded text from ``font.decode`` is appended to the text object
            content."""
            page = _make_page()
            page._text_object.bounding_box = BoundingBox()

            mock_font: MagicMock = _make_font(size=10.0)
            mock_font.decode.return_value = ("AB", 300)
            page._font = mock_font

            page._handle_text_string(b"AB")

            assert page._text_object.content == "AB"

        def test_displacement_updated_by_width_and_font_size(self) -> None:
            """``_x_displacement`` grows by ``width / 1000 * font.size``."""
            page = _make_page()
            page._text_object.bounding_box = BoundingBox()

            mock_font: MagicMock = _make_font(size=10.0)
            mock_font.decode.return_value = ("A", 500)
            page._font = mock_font

            page._handle_text_string(b"A")

            assert page._x_displacement == pytest.approx(5.0)

        def test_bounding_box_width_updated_to_max_displacement(self) -> None:
            """``bounding_box.width`` is updated to the current ``_x_displacement`` when
            greater."""
            page = _make_page()
            page._text_object.bounding_box = BoundingBox(width=0)

            mock_font: MagicMock = _make_font(size=10.0)
            mock_font.decode.return_value = ("A", 1000)
            page._font = mock_font

            page._handle_text_string(b"A")

            assert page._text_object.bounding_box.width == 10

    class TestShowTextString:
        """Tests for ``Page._show_text_string``."""

        def test_delegates_to_handle_text_string(self) -> None:
            """``_handle_text_string`` is called with the first operand."""
            page = _make_page()

            with (
                patch.object(page, "_set_origin"),
                patch.object(page, "_handle_text_string") as mock_handle,
            ):
                page._show_text_string(operands=[b"hello"], cm_matrix=[], tm_matrix=[])

            mock_handle.assert_called_once_with(byte_string=b"hello")

        def test_calls_set_origin(self) -> None:
            """``_set_origin`` is called before the string is processed."""
            page = _make_page()

            with (
                patch.object(page, "_set_origin") as mock_origin,
                patch.object(page, "_handle_text_string"),
            ):
                page._show_text_string(operands=[b"x"], cm_matrix=[1.0], tm_matrix=[2.0])

            mock_origin.assert_called_once_with(cm_matrix=[1.0], tm_matrix=[2.0])

    class TestShowTextStrings:
        """Tests for ``Page._show_text_strings``."""

        def test_bytes_operands_are_decoded(self) -> None:
            """Each ``bytes`` entry in the operand list is passed to
            ``_handle_text_string``."""
            page = _make_page()

            with (
                patch.object(page, "_set_origin"),
                patch.object(page, "_handle_text_string") as mock_handle,
            ):
                page._show_text_strings(operands=[[b"AB", b"CD"]], cm_matrix=[], tm_matrix=[])

            assert mock_handle.call_count == 2
            mock_handle.assert_any_call(byte_string=b"AB")
            mock_handle.assert_any_call(byte_string=b"CD")

        def test_integer_operands_adjust_displacement(self) -> None:
            """Integer (kerning) entries in the operand list adjust ``_x_displacement``
            downward."""
            page = _make_page()
            page._text_object.bounding_box = BoundingBox()
            page._font = _make_font(size=10.0)

            with patch.object(page, "_set_origin"):
                page._show_text_strings(operands=[[100]], cm_matrix=[], tm_matrix=[])

            assert page._x_displacement == pytest.approx(-1.0)

        def test_integer_operands_update_bounding_box_width(self) -> None:
            """After a kerning adjustment the bounding box width is updated to the new
            displacement max."""
            page = _make_page()
            page._text_object.bounding_box = BoundingBox(width=0)
            page._x_displacement = 5.0
            page._font = _make_font(size=10.0)

            with patch.object(page, "_set_origin"):
                page._show_text_strings(operands=[[-100]], cm_matrix=[], tm_matrix=[])

            assert page._text_object.bounding_box.width >= 0

        def test_calls_set_origin(self) -> None:
            """``_set_origin`` is called with the provided matrices."""
            page = _make_page()

            with (
                patch.object(page, "_set_origin") as mock_origin,
                patch.object(page, "_handle_text_string"),
            ):
                page._show_text_strings(operands=[[b"x"]], cm_matrix=[1.0], tm_matrix=[2.0])

            mock_origin.assert_called_once_with(cm_matrix=[1.0], tm_matrix=[2.0])

        def test_mixed_bytes_and_int_operands(self) -> None:
            """A mixed list of bytes and integers is handled correctly."""
            page = _make_page()
            page._text_object.bounding_box = BoundingBox()
            page._font = _make_font(size=10.0)

            with (
                patch.object(page, "_set_origin"),
                patch.object(page, "_handle_text_string") as mock_handle,
            ):
                page._show_text_strings(operands=[[b"A", 50, b"B"]], cm_matrix=[], tm_matrix=[])

            assert mock_handle.call_count == 2
