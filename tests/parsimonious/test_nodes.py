import datetime
from enum import StrEnum
from types import NoneType
from typing import Annotated, Literal, Union
from unittest.mock import MagicMock, patch

import pytest
from parsimonious.grammar import Grammar as ParsimoniousGrammar
from parsimonious.nodes import Node

from pa_record_retriever.parsimonious.nodes import BaseModelNotFoundError, NodeVisitor
from pa_record_retriever.pydantic import BaseModel
from pa_record_retriever.pypdf.enum import DelimiterGlyph


class _SampleStrEnum(StrEnum):
    """A ``StrEnum`` for testing string enum type detection."""

    VALUE_A = "a"
    VALUE_B = "b"


class _ChildModel(BaseModel):
    """A minimal ``BaseModel`` subclass used as a nested model in tests."""

    value: str


class _ModelWithListOfModels(BaseModel):
    """A model containing a list of nested ``_ChildModel`` instances."""

    children: list[_ChildModel]


class _ModelWithOptionalModel(BaseModel):
    """A model containing an optional ``_ChildModel`` field."""

    child: _ChildModel | None = None


class _ModelWithUnsupportedField(BaseModel):
    """A model containing a ``dict`` field, which ``NodeVisitor`` does not support."""

    data: dict


class TestBaseModelNotFoundError:
    """Tests for the ``BaseModelNotFoundError`` exception class."""

    def test_default_message(self) -> None:
        """The default message is set correctly when no argument is provided."""
        assert str(BaseModelNotFoundError()) == "BaseModel class not found or invalid."

    def test_custom_message(self) -> None:
        """A custom message is preserved when passed to the constructor."""
        assert str(BaseModelNotFoundError("custom")) == "custom"

    def test_is_exception(self) -> None:
        """``BaseModelNotFoundError`` is a subclass of ``Exception``."""
        assert isinstance(BaseModelNotFoundError(), Exception)


class TestNodeVisitor:
    """Tests for the ``NodeVisitor`` class."""

    class TestIsSubclass:
        """Tests for ``NodeVisitor._issubclass``."""

        def test_returns_true_for_valid_subclass(self) -> None:
            """Returns ``True`` when the first argument is a subclass of the second."""
            assert NodeVisitor._issubclass(_ChildModel, BaseModel) is True

        def test_returns_true_for_same_class(self) -> None:
            """Returns ``True`` when both arguments are the same class."""
            assert NodeVisitor._issubclass(BaseModel, BaseModel) is True

        def test_returns_false_for_non_class_string(self) -> None:
            """Returns ``False`` when the first argument is not a class."""
            assert NodeVisitor._issubclass("not a class", BaseModel) is False

        def test_returns_false_for_unrelated_class(self) -> None:
            """Returns ``False`` for a class unrelated to ``BaseModel``."""
            assert NodeVisitor._issubclass(int, BaseModel) is False

        def test_returns_false_for_none(self) -> None:
            """Returns ``False`` when ``None`` is passed as the first argument."""
            assert NodeVisitor._issubclass(None, BaseModel) is False

        def test_returns_false_for_model_instance(self) -> None:
            """Returns ``False`` when passed an instance rather than a class."""
            assert NodeVisitor._issubclass(_ChildModel(value="x"), BaseModel) is False

    class TestIsUnion:
        """Tests for ``NodeVisitor._is_union``."""

        def test_pipe_union_is_union(self) -> None:
            """A ``X | Y`` union type is recognised as a union."""
            assert NodeVisitor._is_union(str | None) is True

        def test_typing_union_is_union(self) -> None:
            """A ``typing.Union`` annotation is recognised as a union."""
            assert NodeVisitor._is_union(Union[str, None]) is True  # noqa: UP007

        def test_plain_str_not_union(self) -> None:
            """A bare ``str`` annotation is not a union."""
            assert NodeVisitor._is_union(str) is False

        def test_plain_int_not_union(self) -> None:
            """A bare ``int`` annotation is not a union."""
            assert NodeVisitor._is_union(int) is False

        def test_none_type_not_union(self) -> None:
            """``NoneType`` alone is not a union."""
            assert NodeVisitor._is_union(NoneType) is False

    class TestIsStr:
        """Tests for ``NodeVisitor._is_str``."""

        def test_plain_str(self) -> None:
            """``str`` is treated as a string type."""
            assert NodeVisitor._is_str(str) is True

        def test_literal_str(self) -> None:
            """A ``Literal`` of string values is treated as a string type."""
            assert NodeVisitor._is_str(Literal["a", "b"]) is True

        def test_str_enum_subclass(self) -> None:
            """A ``StrEnum`` subclass is treated as a string type."""
            assert NodeVisitor._is_str(_SampleStrEnum) is True

        def test_annotated_str(self) -> None:
            """``Annotated[str, ...]`` is treated as a string type."""
            assert NodeVisitor._is_str(Annotated[str, "meta"]) is True

        def test_optional_str(self) -> None:
            """``str | None`` is treated as a string type."""
            assert NodeVisitor._is_str(str | None) is True

        def test_union_of_literal_and_none(self) -> None:
            """A union of a string ``Literal`` and ``None`` is treated as a string
            type."""
            assert NodeVisitor._is_str(Literal["x"] | None) is True

        def test_int_not_str(self) -> None:
            """``int`` is not a string type."""
            assert NodeVisitor._is_str(int) is False

        def test_date_not_str(self) -> None:
            """``datetime.date`` is not a string type."""
            assert NodeVisitor._is_str(datetime.date) is False

        def test_literal_of_ints_not_str(self) -> None:
            """A ``Literal`` of integer values is not a string type."""
            assert NodeVisitor._is_str(Literal[1, 2]) is False

        def test_union_str_int_not_str(self) -> None:
            """A union including a non-string type is not a string type."""
            assert NodeVisitor._is_str(str | int) is False

        def test_list_of_str_not_str(self) -> None:
            """``list[str]`` is not a string type."""
            assert NodeVisitor._is_str(list[str]) is False

    class TestIsDate:
        """Tests for ``NodeVisitor._is_date``."""

        def test_plain_date(self) -> None:
            """``datetime.date`` is treated as a date type."""
            assert NodeVisitor._is_date(datetime.date) is True

        def test_optional_date(self) -> None:
            """``datetime.date | None`` is treated as a date type."""
            assert NodeVisitor._is_date(datetime.date | None) is True

        def test_str_not_date(self) -> None:
            """``str`` is not a date type."""
            assert NodeVisitor._is_date(str) is False

        def test_datetime_not_date(self) -> None:
            """``datetime.datetime`` is not treated as a date type."""
            assert NodeVisitor._is_date(datetime.datetime) is False

        def test_union_date_str_not_date(self) -> None:
            """A union including a non-date type is not a date type."""
            assert NodeVisitor._is_date(datetime.date | str) is False

    class TestIsInt:
        """Tests for ``NodeVisitor._is_int``."""

        def test_plain_int(self) -> None:
            """``int`` is treated as an integer type."""
            assert NodeVisitor._is_int(int) is True

        def test_optional_int(self) -> None:
            """``int | None`` is treated as an integer type."""
            assert NodeVisitor._is_int(int | None) is True

        def test_str_not_int(self) -> None:
            """``str`` is not an integer type."""
            assert NodeVisitor._is_int(str) is False

        def test_float_not_int(self) -> None:
            """``float`` is not an integer type."""
            assert NodeVisitor._is_int(float) is False

        def test_union_int_str_not_int(self) -> None:
            """A union including a non-integer type is not an integer type."""
            assert NodeVisitor._is_int(int | str) is False

    class TestIsFloat:
        """Tests for ``NodeVisitor._is_float``."""

        def test_plain_float(self) -> None:
            """``float`` is treated as a float type."""
            assert NodeVisitor._is_float(float) is True

        def test_optional_float(self) -> None:
            """``float | None`` is treated as a float type."""
            assert NodeVisitor._is_float(float | None) is True

        def test_str_not_float(self) -> None:
            """``str`` is not a float type."""
            assert NodeVisitor._is_float(str) is False

        def test_int_not_float(self) -> None:
            """``int`` is not a float type."""
            assert NodeVisitor._is_float(int) is False

        def test_union_float_str_not_float(self) -> None:
            """A union including a non-float type is not a float type."""
            assert NodeVisitor._is_float(float | str) is False

    class TestIsList:
        """Tests for ``NodeVisitor._is_list``."""

        def test_list_of_str(self) -> None:
            """``list[str]`` is treated as a list type."""
            assert NodeVisitor._is_list(list[str]) is True

        def test_list_of_int(self) -> None:
            """``list[int]`` is treated as a list type."""
            assert NodeVisitor._is_list(list[int]) is True

        def test_plain_str_not_list(self) -> None:
            """``str`` is not a list type."""
            assert NodeVisitor._is_list(str) is False

        def test_tuple_not_list(self) -> None:
            """``tuple`` is not a list type."""
            assert NodeVisitor._is_list(tuple[str, ...]) is False

        def test_dict_not_list(self) -> None:
            """``dict`` is not a list type."""
            assert NodeVisitor._is_list(dict[str, str]) is False

    class TestIsModel:
        """Tests for ``NodeVisitor._is_model``."""

        def test_basemodel_subclass(self) -> None:
            """A ``BaseModel`` subclass is treated as a model type."""
            assert NodeVisitor._is_model(_ChildModel) is True

        def test_basemodel_itself(self) -> None:
            """``BaseModel`` itself is treated as a model type."""
            assert NodeVisitor._is_model(BaseModel) is True

        def test_optional_model(self) -> None:
            """``Model | None`` is treated as a model type."""
            assert NodeVisitor._is_model(_ChildModel | None) is True

        def test_str_not_model(self) -> None:
            """``str`` is not a model type."""
            assert NodeVisitor._is_model(str) is False

        def test_int_not_model(self) -> None:
            """``int`` is not a model type."""
            assert NodeVisitor._is_model(int) is False

        def test_list_not_model(self) -> None:
            """``list[Model]`` is not itself a model type."""
            assert NodeVisitor._is_model(list[_ChildModel]) is False

        def test_union_model_with_non_model_not_model(self) -> None:
            """A union of a model and a non-model/non-``None`` type is not a model
            type."""
            assert NodeVisitor._is_model(_ChildModel | str) is False

    class TestIsListOfModel:
        """Tests for ``NodeVisitor._is_list_of_model``."""

        def test_list_of_model(self) -> None:
            """``list[Model]`` is treated as a list-of-model type."""
            assert NodeVisitor._is_list_of_model(list[_ChildModel]) is True

        def test_list_of_str_not_list_of_model(self) -> None:
            """``list[str]`` is not a list-of-model type."""
            assert NodeVisitor._is_list_of_model(list[str]) is False

        def test_plain_model_not_list_of_model(self) -> None:
            """A bare model class is not a list-of-model type."""
            assert NodeVisitor._is_list_of_model(_ChildModel) is False

        def test_optional_list_of_model_not_handled(self) -> None:
            """``list[Model] | None`` is not treated as a list-of-model type."""
            assert NodeVisitor._is_list_of_model(list[_ChildModel] | None) is False

    class TestFlatten:
        """Tests for ``NodeVisitor.flatten``."""

        def test_empty_input_yields_nothing(self) -> None:
            """An empty list produces no output."""
            assert list(NodeVisitor.flatten([])) == []

        def test_node_instances_are_skipped(self) -> None:
            """``Node`` instances are filtered out of the output."""
            mock_node = MagicMock(spec=Node)
            assert list(NodeVisitor.flatten([mock_node])) == []

        def test_dict_yielded_directly(self) -> None:
            """A dict is yielded without recursing into it."""
            d = {"key": "value"}
            assert list(NodeVisitor.flatten([d])) == [d]

        def test_string_yielded_directly(self) -> None:
            """A string is yielded without iterating over its characters."""
            assert list(NodeVisitor.flatten(["hello"])) == ["hello"]

        def test_bytes_yielded_directly(self) -> None:
            """A bytes object is yielded without iterating over its bytes."""
            assert list(NodeVisitor.flatten([b"data"])) == [b"data"]

        def test_nested_list_flattened(self) -> None:
            """Nested lists are recursively flattened into a single sequence."""
            assert list(NodeVisitor.flatten([[1, 2], [3, 4]])) == [1, 2, 3, 4]

        def test_node_inside_nested_list_skipped(self) -> None:
            """``Node`` instances inside nested lists are also skipped."""
            mock_node = MagicMock(spec=Node)
            assert list(NodeVisitor.flatten([[mock_node, 1], 2])) == [1, 2]

        def test_mixed_types(self) -> None:
            """Mixed input of nodes, dicts, strings and lists is flattened correctly."""
            mock_node = MagicMock(spec=Node)
            d = {"k": "v"}
            result = list(NodeVisitor.flatten([mock_node, d, "text", [42]]))
            assert result == [d, "text", 42]

        def test_deeply_nested(self) -> None:
            """Deeply nested lists are fully flattened."""
            assert list(NodeVisitor.flatten([[[1, 2], 3], [4]])) == [1, 2, 3, 4]

    class TestGetFields:
        """Tests for ``NodeVisitor._get_fields``."""

        def test_plain_field_name_and_type(self) -> None:
            """A plain field yields its name and type annotation."""

            class M(BaseModel):
                name: str

            fields = dict(NodeVisitor._get_fields(M))
            assert "name" in fields
            assert fields["name"] is str

        def test_validation_alias_replaces_field_name(self) -> None:
            """A ``validation_alias`` is used instead of the attribute name."""
            from pydantic import Field

            class M(BaseModel):
                name: str = Field(validation_alias="Name")

            fields = dict(NodeVisitor._get_fields(M))
            assert "Name" in fields
            assert "name" not in fields

        def test_alias_choices_yields_each_choice(self) -> None:
            """Each choice in an ``AliasChoices`` is yielded as a separate entry."""
            from pydantic import AliasChoices, Field

            class M(BaseModel):
                name: str = Field(validation_alias=AliasChoices("Name", "n"))

            names = [n for n, _ in NodeVisitor._get_fields(M)]
            assert "Name" in names
            assert "n" in names

        def test_plain_alias_replaces_field_name(self) -> None:
            """A plain ``alias`` is used instead of the attribute name."""
            from pydantic import Field

            class M(BaseModel):
                name: str = Field(alias="Name")

            fields = dict(NodeVisitor._get_fields(M))
            assert "Name" in fields

        def test_multiple_fields_all_returned(self) -> None:
            """All fields in a model are yielded."""

            class M(BaseModel):
                name: str
                count: int

            fields = dict(NodeVisitor._get_fields(M))
            assert "name" in fields
            assert "count" in fields

    class TestGetListFields:
        """Tests for ``NodeVisitor._get_list_fields``."""

        def test_identifies_list_typed_field(self) -> None:
            """Fields with a ``list`` annotation are returned; others are excluded."""

            class M(BaseModel):
                items: list[str]
                name: str

            result = NodeVisitor._get_list_fields(M)
            assert "items" in result
            assert "name" not in result

        def test_returns_empty_list_when_no_list_fields(self) -> None:
            """An empty list is returned when the model has no list-typed fields."""

            class M(BaseModel):
                name: str

            assert NodeVisitor._get_list_fields(M) == []

        def test_multiple_list_fields(self) -> None:
            """All list-typed fields are returned when there are several."""

            class M(BaseModel):
                names: list[str]
                counts: list[int]

            result = NodeVisitor._get_list_fields(M)
            assert "names" in result
            assert "counts" in result

    class TestCreateVisitors:
        """Tests for ``NodeVisitor._create_visitors``."""

        def test_raises_for_none_model_class(self) -> None:
            """``BaseModelNotFoundError`` is raised when ``model_class`` is ``None``."""

            class V(NodeVisitor):
                pass

            v = object.__new__(V)
            with pytest.raises(BaseModelNotFoundError):
                v._create_visitors(None)

        def test_raises_for_non_basemodel_class(self) -> None:
            """``BaseModelNotFoundError`` is raised for a non-``BaseModel`` class."""

            class V(NodeVisitor):
                pass

            v = object.__new__(V)
            with pytest.raises(BaseModelNotFoundError):
                v._create_visitors(str)

        def test_str_field_creates_visit_method(self) -> None:
            """A ``str`` field on the model generates a ``visit_<field>`` method."""

            class M(BaseModel):
                name: str

            class V(NodeVisitor):
                model_class = M

            V()
            assert hasattr(V, "visit_name")

        def test_int_field_creates_visit_method(self) -> None:
            """An ``int`` field on the model generates a ``visit_<field>`` method."""

            class M(BaseModel):
                count: int

            class V(NodeVisitor):
                model_class = M

            V()
            assert hasattr(V, "visit_count")

        def test_float_field_creates_visit_method(self) -> None:
            """A ``float`` field on the model generates a ``visit_<field>`` method."""

            class M(BaseModel):
                score: float

            class V(NodeVisitor):
                model_class = M

            V()
            assert hasattr(V, "visit_score")

        def test_date_field_creates_visit_method(self) -> None:
            """A ``datetime.date`` field on the model generates a ``visit_<field>``
            method."""

            class M(BaseModel):
                dob: datetime.date

            class V(NodeVisitor):
                model_class = M

            V()
            assert hasattr(V, "visit_dob")

        def test_model_field_creates_visit_method(self) -> None:
            """A nested ``BaseModel`` field generates a ``visit_<field>`` method."""

            class M(BaseModel):
                child: _ChildModel

            class V(NodeVisitor):
                model_class = M

            V()
            assert hasattr(V, "visit_child")

        def test_list_of_model_field_creates_visit_method(self) -> None:
            """A ``list[Model]`` field generates a ``visit_<field>`` method."""

            class V(NodeVisitor):
                model_class = _ModelWithListOfModels

            V()
            assert hasattr(V, "visit_children")

        def test_list_of_primitives_creates_visit_method(self) -> None:
            """A ``list[str]`` field generates a ``visit_<field>`` method."""

            class M(BaseModel):
                items: list[str]

            class V(NodeVisitor):
                model_class = M

            V()
            assert hasattr(V, "visit_items")

        def test_optional_model_field_creates_visit_method(self) -> None:
            """An optional ``Model | None`` field generates a ``visit_<field>``
            method."""

            class V(NodeVisitor):
                model_class = _ModelWithOptionalModel

            V()
            assert hasattr(V, "visit_child")

        def test_multi_model_union_field_logs_warning(self) -> None:
            """A union of multiple model types logs a warning and creates no visitor."""

            class OtherModel(BaseModel):
                label: str

            class M(BaseModel):
                item: _ChildModel | OtherModel

            with patch("pa_ujs_document_parser.parsimonious.nodes.logger") as mock_logger:

                class V(NodeVisitor):
                    model_class = M

                V()
            mock_logger.warning.assert_called()

        def test_unsupported_field_type_logs_warning(self) -> None:
            """An unsupported field type logs a warning and creates no visitor."""
            with patch("pa_ujs_document_parser.parsimonious.nodes.logger") as mock_logger:

                class V(NodeVisitor):
                    model_class = _ModelWithUnsupportedField

                V()
            mock_logger.warning.assert_called()

    class TestAddStrVisitor:
        """Tests for ``NodeVisitor._add_str_visitor``."""

        def test_stripped_text_returned_as_dict(self) -> None:
            """Leading and trailing whitespace is stripped from the node text."""

            class V(NodeVisitor):
                pass

            V._add_str_visitor("field")
            node = MagicMock()
            node.text = "  hello  "
            assert V.visit_field(None, node, []) == {"field": "hello"}

        def test_return_delimiter_replaced_with_space(self) -> None:
            """The ``RETURN`` delimiter glyph is replaced with a single space."""

            class V(NodeVisitor):
                pass

            V._add_str_visitor("field")
            node = MagicMock()
            node.text = f"foo{DelimiterGlyph.RETURN}bar"
            assert V.visit_field(None, node, []) == {"field": "foo bar"}

        def test_whitespace_around_delimiter_collapsed(self) -> None:
            """Surrounding whitespace around the ``RETURN`` delimiter is collapsed."""

            class V(NodeVisitor):
                pass

            V._add_str_visitor("field")
            node = MagicMock()
            node.text = f"a  {DelimiterGlyph.RETURN}  b"
            assert V.visit_field(None, node, []) == {"field": "a b"}

        def test_empty_text_returns_empty_string(self) -> None:
            """Whitespace-only text results in an empty string value."""

            class V(NodeVisitor):
                pass

            V._add_str_visitor("field")
            node = MagicMock()
            node.text = "   "
            assert V.visit_field(None, node, []) == {"field": ""}

    class TestAddDateVisitor:
        """Tests for ``NodeVisitor._add_date_visitor``."""

        def test_parses_slash_separated_date(self) -> None:
            """A slash-separated date string is parsed into a ``datetime.date``."""

            class V(NodeVisitor):
                pass

            V._add_date_visitor("dob")
            node = MagicMock()
            node.text = "01/15/2023"
            assert V.visit_dob(None, node, []) == {"dob": datetime.date(2023, 1, 15)}

        def test_strips_whitespace_before_parsing(self) -> None:
            """Surrounding whitespace is stripped before the date string is parsed."""

            class V(NodeVisitor):
                pass

            V._add_date_visitor("dob")
            node = MagicMock()
            node.text = "  2023-01-15  "
            assert V.visit_dob(None, node, []) == {"dob": datetime.date(2023, 1, 15)}

    class TestAddIntVisitor:
        """Tests for ``NodeVisitor._add_int_visitor``."""

        def test_parses_plain_integer(self) -> None:
            """A plain integer string is converted to an ``int``."""

            class V(NodeVisitor):
                pass

            V._add_int_visitor("count")
            node = MagicMock()
            node.text = "42"
            assert V.visit_count(None, node, []) == {"count": 42}

        def test_removes_comma_separators(self) -> None:
            """Comma thousand-separators are removed before conversion."""

            class V(NodeVisitor):
                pass

            V._add_int_visitor("count")
            node = MagicMock()
            node.text = "1,000,000"
            assert V.visit_count(None, node, []) == {"count": 1000000}

        def test_strips_surrounding_whitespace(self) -> None:
            """Surrounding whitespace is stripped before conversion."""

            class V(NodeVisitor):
                pass

            V._add_int_visitor("count")
            node = MagicMock()
            node.text = "  99  "
            assert V.visit_count(None, node, []) == {"count": 99}

    class TestAddFloatVisitor:
        """Tests for ``NodeVisitor._add_float_visitor``."""

        def test_parses_plain_float(self) -> None:
            """A plain float string is converted to a ``float``."""

            class V(NodeVisitor):
                pass

            V._add_float_visitor("score")
            node = MagicMock()
            node.text = "3.14"
            assert V.visit_score(None, node, []) == {"score": 3.14}

        def test_removes_comma_separators(self) -> None:
            """Comma thousand-separators are removed before conversion."""

            class V(NodeVisitor):
                pass

            V._add_float_visitor("score")
            node = MagicMock()
            node.text = "1,234.56"
            assert V.visit_score(None, node, []) == {"score": 1234.56}

        def test_strips_surrounding_whitespace(self) -> None:
            """Surrounding whitespace is stripped before conversion."""

            class V(NodeVisitor):
                pass

            V._add_float_visitor("score")
            node = MagicMock()
            node.text = "  2.5  "
            assert V.visit_score(None, node, []) == {"score": 2.5}

    class TestAddListVisitor:
        """Tests for ``NodeVisitor._add_list_visitor``."""

        def test_list_of_str_delegates_to_str_visitor(self) -> None:
            """``list[str]`` creates a string visitor for the field."""

            class V(NodeVisitor):
                pass

            V._add_list_visitor("items", list[str])
            node = MagicMock()
            node.text = "hello"
            assert V.visit_items(None, node, []) == {"items": "hello"}

        def test_list_of_int_delegates_to_int_visitor(self) -> None:
            """``list[int]`` creates an integer visitor for the field."""

            class V(NodeVisitor):
                pass

            V._add_list_visitor("nums", list[int])
            node = MagicMock()
            node.text = "7"
            assert V.visit_nums(None, node, []) == {"nums": 7}

        def test_list_of_float_delegates_to_float_visitor(self) -> None:
            """``list[float]`` creates a float visitor for the field."""

            class V(NodeVisitor):
                pass

            V._add_list_visitor("vals", list[float])
            node = MagicMock()
            node.text = "1.5"
            assert V.visit_vals(None, node, []) == {"vals": 1.5}

        def test_list_of_date_delegates_to_date_visitor(self) -> None:
            """``list[datetime.date]`` creates a date visitor for the field."""

            class V(NodeVisitor):
                pass

            V._add_list_visitor("dates", list[datetime.date])
            node = MagicMock()
            node.text = "01/15/2023"
            result = V.visit_dates(None, node, [])
            assert result == {"dates": datetime.date(2023, 1, 15)}

        def test_unsupported_list_item_type_sets_no_visitor(self) -> None:
            """An unsupported item type results in no visitor being set."""

            class V(NodeVisitor):
                pass

            V._add_list_visitor("data", list[dict])
            assert not hasattr(V, "visit_data")

    class TestAddModelVisitor:
        """Tests for ``NodeVisitor._add_model_visitor``."""

        def test_include_key_wraps_result(self) -> None:
            """When ``include_key=True``, the result is nested under the field name."""

            class M(BaseModel):
                name: str

            class V(NodeVisitor):
                pass

            V._add_model_visitor("model", M, include_key=True)
            node = MagicMock()
            result = V.visit_model(None, node, [{"name": "Alice"}])
            assert result == {"model": {"name": "Alice"}}

        def test_include_key_false_returns_flat_dict(self) -> None:
            """When ``include_key=False``, the result dict is returned directly."""

            class M(BaseModel):
                name: str

            class V(NodeVisitor):
                pass

            V._add_model_visitor("root", M, include_key=False)
            node = MagicMock()
            result = V.visit_root(None, node, [{"name": "Alice"}])
            assert result == {"name": "Alice"}

        def test_list_field_appends_scalar_values(self) -> None:
            """Scalar values for a list field are appended into the list."""

            class M(BaseModel):
                items: list[str]

            class V(NodeVisitor):
                pass

            V._add_model_visitor("m", M)
            node = MagicMock()
            result = V.visit_m(None, node, [{"items": "a"}, {"items": "b"}])
            assert result == {"m": {"items": ["a", "b"]}}

        def test_list_field_extends_with_list_value(self) -> None:
            """A list value for a list field is extended into the accumulator."""

            class M(BaseModel):
                items: list[str]

            class V(NodeVisitor):
                pass

            V._add_model_visitor("m", M)
            node = MagicMock()
            result = V.visit_m(None, node, [{"items": ["a", "b"]}, {"items": "c"}])
            assert result == {"m": {"items": ["a", "b", "c"]}}

        def test_duplicate_str_field_concatenated_with_space(self) -> None:
            """Duplicate string field values are joined with a space."""

            class M(BaseModel):
                name: str

            class V(NodeVisitor):
                pass

            V._add_model_visitor("m", M)
            node = MagicMock()
            result = V.visit_m(None, node, [{"name": "Hello"}, {"name": "World"}])
            assert result == {"m": {"name": "Hello World"}}

        def test_multi_key_child_dict_logs_warning(self) -> None:
            """A child dict with more than one key logs a warning and is skipped."""

            class M(BaseModel):
                name: str

            class V(NodeVisitor):
                pass

            V._add_model_visitor("m", M)
            node = MagicMock()
            with patch("pa_ujs_document_parser.parsimonious.nodes.logger") as mock_logger:
                V.visit_m(None, node, [{"name": "Alice", "extra": "x"}])
            mock_logger.warning.assert_called_once()

        def test_non_dict_child_logs_warning(self) -> None:
            """A non-dict child value logs a warning."""

            class M(BaseModel):
                name: str

            class V(NodeVisitor):
                pass

            V._add_model_visitor("m", M)
            node = MagicMock()
            with patch("pa_ujs_document_parser.parsimonious.nodes.logger") as mock_logger:
                V.visit_m(None, node, ["not a dict"])
            mock_logger.warning.assert_called_once()

        def test_duplicate_non_str_field_logs_warning(self) -> None:
            """A duplicate non-string field value logs a warning."""

            class M(BaseModel):
                count: int

            class V(NodeVisitor):
                pass

            V._add_model_visitor("m", M)
            node = MagicMock()
            with patch("pa_ujs_document_parser.parsimonious.nodes.logger") as mock_logger:
                V.visit_m(None, node, [{"count": 1}, {"count": 2}])
            mock_logger.warning.assert_called_once()

        def test_empty_visited_children_returns_empty_model(self) -> None:
            """No children results in an empty model dict."""

            class M(BaseModel):
                name: str

            class V(NodeVisitor):
                pass

            V._add_model_visitor("m", M)
            node = MagicMock()
            result = V.visit_m(None, node, [])
            assert result == {"m": {}}

    class TestGenericVisit:
        """Tests for ``NodeVisitor.generic_visit``."""

        def test_returns_visited_children_when_truthy(self) -> None:
            """Non-empty ``visited_children`` is returned as-is."""

            class M(BaseModel):
                name: str

            class V(NodeVisitor):
                model_class = M

            v = V()
            node = MagicMock(spec=Node)
            assert v.generic_visit(node, ["child"]) == ["child"]

        def test_returns_node_when_visited_children_empty(self) -> None:
            """The node itself is returned when ``visited_children`` is empty."""

            class M(BaseModel):
                name: str

            class V(NodeVisitor):
                model_class = M

            v = V()
            node = MagicMock(spec=Node)
            assert v.generic_visit(node, []) is node

    class TestSerialize:
        """Tests for ``NodeVisitor.serialize``."""

        def test_serializes_str_field_to_model(self) -> None:
            """A parsed tree is serialized into the correct ``BaseModel`` instance."""

            class M(BaseModel):
                name: str

            class V(NodeVisitor):
                model_class = M

            grammar = ParsimoniousGrammar('root = name\nname = ~r"[a-z]+"')
            tree = grammar.parse("alice")
            result = V().serialize(tree)
            assert isinstance(result, M)
            assert result.name == "alice"

        def test_serializes_int_field_to_model(self) -> None:
            """An integer field is correctly parsed and coerced in the model."""

            class M(BaseModel):
                count: int

            class V(NodeVisitor):
                model_class = M

            grammar = ParsimoniousGrammar('root = count\ncount = ~r"[0-9]+"')
            tree = grammar.parse("42")
            result = V().serialize(tree)
            assert isinstance(result, M)
            assert result.count == 42
