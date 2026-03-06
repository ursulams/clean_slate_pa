from enum import StrEnum

import httpx
from pydantic import Field
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from pa_ujs_document_parser.pydantic import BaseModel

retry_x3 = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type(httpx.HTTPError),
    reraise=True,
)
"""
Tenacity retry decorator that retries up to 3 times on ``httpx.HTTPError``, with
exponential backoff between 4 and 10 seconds.

The original exception is re-raised if all attempts fail.

"""


class InvalidResponseError(Exception):
    """Exception raised for invalid HTTP responses."""

    def __init__(self, message: str):
        super().__init__(message)


class InvalidPageContentError(ValueError):
    """Exception raised when page content is invalid or unexpected."""

    def __init__(self, message: str):
        super().__init__(message)


class RequestHeaders(BaseModel):
    """Base model for HTTP request headers sent to the UJS portal."""

    user_agent: str = Field(
        default="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
        serialization_alias="User-Agent",
    )
    """The `User-Agent` header, defaulting to a common browser user agent string."""

    accept: str = "*/*"
    """The `Accept` header, defaulting to "*/*"."""


class ContentType(StrEnum):
    """Enumeration representing common Content-Type header values."""

    JSON = "application/json"
    FORM_URLENCODED = "application/x-www-form-urlencoded"
    MULTIPART_FORM_DATA = "multipart/form-data"
