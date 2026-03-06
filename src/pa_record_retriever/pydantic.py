from typing import Any

from dateutil import parser as date_parser
from pydantic import BaseModel as PydanticBaseModel
from pydantic import ConfigDict


class BaseModel(PydanticBaseModel):
    """
    A subclass of Pydantic's ``BaseModel`` that sets common configuration for all
    derived models.

    Key configuration options:

    - ``extra="ignore"``: Extra fields in input data are silently discarded.
    - ``serialize_by_alias=True``: Serialization uses field aliases where defined.
    - ``str_strip_whitespace=True``: Leading and trailing whitespace is stripped from
      string fields automatically.
    - ``use_attribute_docstrings=True``: Attribute docstrings are used as field
      descriptions.
    - ``use_enum_values=True``: Enum fields are stored and serialized as their raw
      values rather than enum instances.
    - ``validate_by_alias=True`` / ``validate_by_name=True``: Validation accepts both
      the field name and any defined alias.

    """

    model_config = ConfigDict(
        extra="ignore",
        serialize_by_alias=True,
        str_strip_whitespace=True,
        use_attribute_docstrings=True,
        use_enum_values=True,
        validate_by_alias=True,
        validate_by_name=True,
    )

    @staticmethod
    def _str_to_date(value: Any) -> Any:
        """
        Attempts to parse a date from a string and return it as a date object.
        Otherwise, returns the original value.

        Args:
            value (Any): The value to be validated, potentially a string representing a date.

        Returns:
            Any: A datetime.date object if parsing is successful; otherwise, the original value.

        """
        if isinstance(value, str):
            try:
                return date_parser.parse(value).date()
            except date_parser.ParserError:
                pass

        return value
