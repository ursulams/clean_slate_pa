import httpx
import pytest

from pa_record_retriever.requests import (
    ContentType,
    InvalidPageContentError,
    InvalidResponseError,
    RequestHeaders,
    retry_x3,
)


class TestInvalidResponseError:
    """Tests for the ``InvalidResponseError`` exception class."""

    def test_is_exception_subclass(self) -> None:
        """``InvalidResponseError`` is a subclass of ``Exception``."""
        assert issubclass(InvalidResponseError, Exception)

    def test_message_stored(self) -> None:
        """The error message passed at construction is accessible via ``str()``."""
        err = InvalidResponseError("bad response")
        assert "bad response" in str(err)

    def test_can_be_raised_and_caught(self) -> None:
        """``InvalidResponseError`` can be raised and caught by its own type."""
        with pytest.raises(InvalidResponseError, match="bad"):
            raise InvalidResponseError("bad")


class TestInvalidPageContentError:
    """Tests for the ``InvalidPageContentError`` exception class."""

    def test_is_value_error_subclass(self) -> None:
        """``InvalidPageContentError`` is a subclass of ``ValueError``."""
        assert issubclass(InvalidPageContentError, ValueError)

    def test_message_stored(self) -> None:
        """The error message passed at construction is accessible via ``str()``."""
        err = InvalidPageContentError("bad content")
        assert "bad content" in str(err)

    def test_can_be_raised_and_caught_as_value_error(self) -> None:
        """``InvalidPageContentError`` can be caught as a ``ValueError``."""
        with pytest.raises(ValueError, match="bad content"):
            raise InvalidPageContentError("bad content")


class TestRetryX3:
    """Tests for the ``retry_x3`` tenacity decorator."""

    def test_succeeds_on_first_attempt(self) -> None:
        """A function that does not raise is called once and returns normally."""
        call_count: list[int] = [0]

        @retry_x3
        def succeeds() -> str:
            """Returns immediately on first call."""
            call_count[0] += 1
            return "ok"

        result = succeeds()
        assert result == "ok"
        assert call_count[0] == 1

    def test_reraises_after_max_attempts(self) -> None:
        """After three failures the original ``HTTPError`` is re-raised."""

        @retry_x3
        def always_fails() -> None:
            """Always raises an ``httpx.ConnectError``."""
            raise httpx.ConnectError("connection refused")

        with pytest.raises(httpx.ConnectError):
            always_fails()

    def test_does_not_retry_non_http_errors(self) -> None:
        """A non-``httpx.HTTPError`` propagates immediately without retrying."""
        call_count: list[int] = [0]

        @retry_x3
        def raises_value_error() -> None:
            """Raises a plain ``ValueError`` on every call."""
            call_count[0] += 1
            raise ValueError("not an http error")

        with pytest.raises(ValueError):
            raises_value_error()

        assert call_count[0] == 1


class TestRequestHeaders:
    """Tests for the ``RequestHeaders`` Pydantic model."""

    def test_default_user_agent_is_mozilla(self) -> None:
        """The default ``user_agent`` starts with ``Mozilla``."""
        headers = RequestHeaders()
        assert headers.user_agent.startswith("Mozilla")

    def test_default_accept_is_wildcard(self) -> None:
        """The default ``accept`` value is ``"*/*"``."""
        headers = RequestHeaders()
        assert headers.accept == "*/*"

    def test_serialization_uses_user_agent_alias(self) -> None:
        """``model_dump`` serializes ``user_agent`` under the ``User-Agent`` key."""
        headers = RequestHeaders()
        dumped = headers.model_dump()
        assert "User-Agent" in dumped

    def test_user_agent_can_be_overridden(self) -> None:
        """A custom ``user_agent`` value is stored and returned correctly."""
        headers = RequestHeaders(user_agent="CustomAgent/1.0")
        assert headers.user_agent == "CustomAgent/1.0"

    def test_accept_can_be_overridden(self) -> None:
        """A custom ``accept`` value is stored and returned correctly."""
        headers = RequestHeaders(accept="application/json")
        assert headers.accept == "application/json"


class TestContentType:
    """Tests for the ``ContentType`` StrEnum."""

    def test_json_value(self) -> None:
        """``JSON`` has the expected MIME type string."""
        assert ContentType.JSON == "application/json"

    def test_form_urlencoded_value(self) -> None:
        """``FORM_URLENCODED`` has the expected MIME type string."""
        assert ContentType.FORM_URLENCODED == "application/x-www-form-urlencoded"

    def test_multipart_form_data_value(self) -> None:
        """``MULTIPART_FORM_DATA`` has the expected MIME type string."""
        assert ContentType.MULTIPART_FORM_DATA == "multipart/form-data"

    def test_members_are_strings(self) -> None:
        """All ``ContentType`` members are instances of ``str``."""
        for member in ContentType:
            assert isinstance(member, str)
