import datetime
from typing import Any

from pa_record_retriever.pydantic import BaseModel


class _MinimalModel(BaseModel):
    """Minimal concrete ``BaseModel`` subclass used in configuration tests."""

    name: str
    value: int = 0


class TestBaseModelConfig:
    """Tests for ``BaseModel`` configuration options."""

    class TestExtraIgnored:
        """Tests that extra fields are silently discarded."""

        def test_extra_field_is_dropped(self) -> None:
            """Extra fields passed during construction are not stored on the model."""
            model = _MinimalModel(name="test", value=1, unexpected="ignored")
            assert not hasattr(model, "unexpected")

        def test_model_fields_unaffected_by_extra(self) -> None:
            """Known fields are still populated when extra fields are present."""
            model = _MinimalModel(name="kept", extra_field="dropped")
            assert model.name == "kept"

    class TestStrStripWhitespace:
        """Tests that leading and trailing whitespace is stripped from string fields."""

        def test_leading_whitespace_stripped(self) -> None:
            """Leading whitespace is removed from string field values."""
            model = _MinimalModel(name="  hello")
            assert model.name == "hello"

        def test_trailing_whitespace_stripped(self) -> None:
            """Trailing whitespace is removed from string field values."""
            model = _MinimalModel(name="hello  ")
            assert model.name == "hello"

        def test_both_sides_stripped(self) -> None:
            """Whitespace on both sides is removed."""
            model = _MinimalModel(name="  hello  ")
            assert model.name == "hello"

        def test_internal_whitespace_preserved(self) -> None:
            """Whitespace within the string is not modified."""
            model = _MinimalModel(name="hello world")
            assert model.name == "hello world"


class TestStrToDate:
    """Tests for ``BaseModel._str_to_date``."""

    class TestStringInput:
        """Tests when the input is a string."""

        def test_parses_iso_date_string(self) -> None:
            """An ISO-format date string is parsed and returned as a ``date`` object."""
            result: Any = BaseModel._str_to_date("2020-01-15")
            assert result == datetime.date(2020, 1, 15)

        def test_parses_slash_date_string(self) -> None:
            """A slash-formatted date string is parsed and returned as a ``date``
            object."""
            result: Any = BaseModel._str_to_date("01/15/2020")
            assert result == datetime.date(2020, 1, 15)

        def test_parses_long_form_date_string(self) -> None:
            """A long-form date string (e.g., 'January 15, 2020') is parsed
            correctly."""
            result: Any = BaseModel._str_to_date("January 15, 2020")
            assert result == datetime.date(2020, 1, 15)

        def test_returns_original_on_parse_failure(self) -> None:
            """An unparseable string is returned unchanged."""
            result: Any = BaseModel._str_to_date("not-a-date")
            assert result == "not-a-date"

        def test_returns_original_on_empty_string(self) -> None:
            """An empty string is returned unchanged (not converted)."""
            result: Any = BaseModel._str_to_date("")
            assert result == ""

    class TestNonStringInput:
        """Tests when the input is not a string."""

        def test_date_object_returned_unchanged(self) -> None:
            """A ``datetime.date`` object is returned without modification."""
            d: datetime.date = datetime.date(2020, 6, 15)
            result: Any = BaseModel._str_to_date(d)
            assert result is d

        def test_none_returned_unchanged(self) -> None:
            """``None`` is returned without modification."""
            result: Any = BaseModel._str_to_date(None)
            assert result is None

        def test_integer_returned_unchanged(self) -> None:
            """An integer is returned without modification."""
            result: Any = BaseModel._str_to_date(42)
            assert result == 42

        def test_datetime_returned_unchanged(self) -> None:
            """A ``datetime.datetime`` object is returned without modification."""
            dt: datetime.datetime = datetime.datetime(2020, 6, 15, 12, 0)
            result: Any = BaseModel._str_to_date(dt)
            assert result is dt

    class TestReturnType:
        """Tests for the return type of ``_str_to_date``."""

        def test_returns_date_not_datetime(self) -> None:
            """The parsed result is a ``datetime.date``, not a ``datetime.datetime``."""
            result: Any = BaseModel._str_to_date("2020-01-15")
            assert type(result) is datetime.date
