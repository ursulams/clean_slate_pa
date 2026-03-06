from __future__ import annotations

import datetime
import os
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
from dateutil import parser as date_parser
from justhtml import JustHTML, Node
from loguru import logger
from pydantic import ConfigDict, Field, field_validator

from pa_ujs_document_parser.models import (
    CaseStatusMixin,
    CaseTypeMixin,
    Constant,
    CountyMixin,
    CourtRequestHeaders,
    CourtType,
    DocketNumberMixin,
    DocketType,
    OtnMixin,
    SearchBy,
)
from pa_ujs_document_parser.requests import ContentType, InvalidPageContentError, InvalidResponseError, retry_x3


class EmptyFieldError(ValueError):
    """Raised when a required string field is empty."""

    def __init__(self, field: str) -> None:
        super().__init__(f"{field!r} must not be empty.")


class DnhMissingError(ValueError):
    """Custom error raised when a required 'dnh' query parameter is missing from a
    URL."""

    def __init__(self) -> None:
        self.message = "URL must contain a populated 'dnh' query string parameter."
        super().__init__(self.message)


class CaseSearchRequestHeaders(CourtRequestHeaders):
    """Represents the request headers used in the Unified Judicial System of
    Pennsylvania case search."""

    referer: str = Constant.BASE_URL + Constant.CASE_SEARCH_ENDPOINT
    """The `Referer` header, set to the case search endpoint."""

    content_type: ContentType = Field(default=ContentType.FORM_URLENCODED, serialization_alias="Content-Type")
    """The `Content-Type` header, set to `application/x-www-form-urlencoded`."""

    cookie: str = Constant.CASE_SEARCH_COOKIE
    """The `Cookie` header, set to a pre-generated cookie string that includes an
    antiforgery token and Google Analytics cookies."""


class CaseFiling(CaseTypeMixin, OtnMixin, CaseStatusMixin, DocketNumberMixin, CountyMixin):
    """Represents the case-level information for a Pennsylvania court case."""

    model_config = ConfigDict(validate_assignment=True)

    filing_date: datetime.date = Field(validation_alias="FilingDate")
    """The filing date of the case."""

    case_caption: str | None = Field(validation_alias="ShortCaption")
    """
    The caption of the case (e.g., "Comm.

    vs. Iverson, Allen").

    """

    defendant_name: str | None = Field(validation_alias="PrimaryParticipantName")
    """The primary defendant's full name in reverse order (e.g., "Iverson, Allen")."""

    defendant_date_of_birth: datetime.date | None = Field(validation_alias="PrimaryParticipantDOB")
    """The defendant's full date of birth."""

    court_office: str | None = Field(validation_alias="CourtOffice")
    """The court office handling the case."""

    complaint_number: str | None = Field(validation_alias="ComplaintNumber")
    """The complaint number."""

    incident_number: str | None = Field(validation_alias="IncidentNumber")
    """The incident number."""

    docket_sheet_url: str | None = None
    """The URL at which the case's docket sheet can be found, including the required DNH
    token."""

    court_summary_url: str | None = None
    """The URL at which the defendant's court summary can be found, including the
    required DNH token."""

    @field_validator("filing_date", "defendant_date_of_birth", mode="before")
    @classmethod
    def parse_date_from_string(cls, value: Any) -> Any:
        """
        Attempts to parse a date from a string and return it as a date object.
        Otherwise, returns the original value unchanged.

        Delegates to ``_str_to_date``.

        Args:
            value (Any): The value to be validated, potentially a string representing a date.

        Returns:
            Any: A ``datetime.date`` object if parsing is successful; otherwise, the original value.

        """
        return cls._str_to_date(value)

    @field_validator("docket_sheet_url", "court_summary_url", mode="after")
    @classmethod
    def validate_dnh_param(cls, value: str | None) -> str | None:
        """
        Ensures that ``docket_sheet_url`` and ``court_summary_url`` contain a populated
        ``dnh`` query string parameter.

        Raises:
            DnhMissingError: If the URL is present but the ``dnh`` parameter is absent
                or empty.

        """
        if value is not None and not parse_qs(urlparse(value).query).get("dnh"):
            raise DnhMissingError

        return value

    @staticmethod
    def _has_records(page: JustHTML) -> bool:
        """
        Determines if the given page contains case filing records.

        Args:
            page (JustHTML): The JustHTML page object containing the case filing data.

        Returns:
            bool: True if the page contains case filing records, False otherwise.

        Raises:
            InvalidPageContentError: If the search results table is not found.

        """
        search_results_table: Node | None = page.query_one(f"table#{Constant.CASE_SEARCH_RESULTS_TABLE_ID}")

        # If invalid content, raise error
        if search_results_table is None:
            raise InvalidPageContentError(message="Case filings table not found.")

        return "no results" not in search_results_table.to_text().lower()

    @staticmethod
    def _get_table_headers(table: Node) -> list[str]:
        """
        Retrieves the table header names from the given page.

        Args:
            table (Node): The Node object representing the table.

        Returns:
            list[str]: A list of table header names.

        Raises:
            InvalidPageContentError: If the table headers are not found.

        """
        table_headers = table.query("th")

        if not table_headers:
            raise InvalidPageContentError(message="Case filings table headers not found.")

        header_names = []
        for header in table_headers:
            header: Node
            if name := header.attrs.get("data-aopc-headername"):
                header_names.append(name)

        return header_names

    @staticmethod
    def _get_records(page: JustHTML) -> list[CaseFiling]:
        """
        Extracts and validates ``CaseFiling`` records from the search results table.

        For each row, cell values are zipped with column headers to construct a
        ``CaseFiling``. ``docket_sheet_url`` and ``court_summary_url`` are parsed
        from anchor tags in the row. ``court_type`` and ``docket_type`` are imputed
        via ``CourtType.from_docket_number`` and ``DocketType.from_docket_number``.
        Duplicate docket numbers are suppressed.

        Args:
            page (JustHTML): The parsed search results page.

        Returns:
            list[CaseFiling]: Deduplicated list of ``CaseFiling`` instances.

        """
        # Get table object
        table: Node = page.query_one(f"table#{Constant.CASE_SEARCH_RESULTS_TABLE_ID}")

        # Get column names and table rows
        header_names = CaseFiling._get_table_headers(table)
        table_rows: list[Node] = table.query("tbody > tr")

        cases = []
        docket_numbers = []

        for row in table_rows:
            # Extract plain-text cell values
            values = []
            for r in row.query("td"):
                r: Node
                value = r.to_text()
                value = None if value == "" else value
                values.append(value)

            # Validate
            case = dict(zip(header_names, values, strict=False))
            case_filing = CaseFiling(**case)

            # Extract URLs for docket sheet and court summary if they exist
            for img in row.query("img"):
                img: Node
                url = img.parent.attrs.get("href", "")
                if "DocketSheet" in url:
                    case_filing.docket_sheet_url = url
                elif "CourtSummary" in url:
                    case_filing.court_summary_url = url

            # Impute court type and docket type from docket number
            if _court_type := CourtType.from_docket_number(case_filing.docket_number):
                case_filing.court_type = _court_type

            if _docket_type := DocketType.from_docket_number(case_filing.docket_number):
                case_filing.docket_type = _docket_type

            # Ignore duplicate docket numbers
            if case_filing.docket_number not in docket_numbers:
                cases.append(case_filing)
                docket_numbers.append(case_filing.docket_number)

        return cases

    @staticmethod
    def _extract_case_filings(html_str: str) -> list[CaseFiling]:
        """
        Parses ``CaseFiling`` records from a raw HTML string returned by the case
        search.

        Delegates record presence detection to ``_has_records`` and record extraction
        to ``_get_records``.

        Args:
            html_str (str): The HTML response body from the case search endpoint.

        Returns:
            list[CaseFiling]: Parsed case filings, or an empty list if the search
                returned no results.

        """
        # Get page tree. Sanitization is disabled because the source is a trusted
        # government website and sanitization strips `data-*` attributes that are
        # required to map table columns to their field names.
        page = JustHTML(html_str, sanitize=False)

        # If no results, return empty list
        if not CaseFiling._has_records(page):
            return []

        # Get records
        return CaseFiling._get_records(page)

    @staticmethod
    def _raise_for_invalid_content(content: str) -> None:
        """
        Raises an InvalidResponseError if the response content is not a string or does
        not contain the expected results table ID.

        Logs a warning if the content indicates that the number of search results exceeds the limit.

        Args:
            content (str): The response content to validate.

        Raises:
            InvalidResponseError: If the content is not a string or does not contain the expected results table ID.

        """
        if not isinstance(content, str):
            raise InvalidResponseError(message="Response object is not a string.")

        if f'id="{Constant.CASE_SEARCH_RESULTS_TABLE_ID}"' not in content:
            raise InvalidResponseError(message="Response HTML is missing the expected case filings table ID.")

        if "please narrow your search" in content.lower():
            logger.warning("Number of case filings exceeds the page load limit, consider different search parameters.")

    @staticmethod
    @retry_x3
    def _fetch(body: dict[str, Any]) -> str:
        """
        Submits a case search POST request to the UJS portal and returns the HTML
        response.

        Constructs the request using ``CaseSearchRequestHeaders`` and posts to the
        ``/CaseSearch`` endpoint. Respects the ``HTTP_PROXY`` environment variable when
        present. Validates the response content before returning.

        Args:
            body (dict[str, Any]): Form data for the POST request, including search
                parameters and the antiforgery token.

        Returns:
            str: The HTML response body containing the search results table.

        Raises:
            httpx.HTTPStatusError: If the server returns an unsuccessful HTTP status code.
            InvalidResponseError: If the response body is missing the expected results table.

        """
        logger.info("Fetching case filings...")

        url = Constant.BASE_URL + "/CaseSearch"
        headers = CaseSearchRequestHeaders().model_dump(exclude_none=True)

        if proxy := os.environ.get("HTTP_PROXY"):
            with httpx.Client(proxy=proxy) as client:
                response = client.post(url=url, headers=headers, data=body, timeout=15)
        else:
            response = httpx.post(url=url, headers=headers, data=body, timeout=15)

        response.raise_for_status()

        html_str = response.text
        CaseFiling._raise_for_invalid_content(html_str)

        logger.info("Case filings fetched successfully.")

        return html_str

    @classmethod
    def from_related_docket_number(cls, docket_number: str) -> list[CaseFiling]:
        """
        Fetches all case filings associated with the given docket number.

        Submits a docket-number search to the UJS portal via ``_fetch`` and parses
        the results via ``_extract_case_filings``.

        Args:
            docket_number (str): The docket number to search for
                (e.g. ``CP-51-CR-0001234-2020``).

        Returns:
            list[CaseFiling]: All matching ``CaseFiling`` instances, or an empty list
                if none are found.

        Raises:
            EmptyFieldError: If ``docket_number`` is empty.
            httpx.HTTPStatusError: If the server returns an unsuccessful HTTP status code.
            InvalidResponseError: If the response body is missing the expected results table.

        """
        if not docket_number:
            raise EmptyFieldError("docket_number")

        body = {
            "SearchBy": str(SearchBy.DOCKET_NUMBER),
            "DocketNumber": docket_number,
            "__RequestVerificationToken": Constant.CASE_SEARCH_TOKEN,
        }

        html_str = cls._fetch(body)
        return cls._extract_case_filings(html_str)

    @classmethod
    def from_defendant(
        cls,
        first_name: str,
        last_name: str,
        date_of_birth: datetime.date | str | None = None,
    ) -> list[CaseFiling]:
        """
        Fetches all criminal case filings associated with the given defendant.

        Submits a participant-name search to the UJS portal via ``_fetch`` and parses
        the results via ``_extract_case_filings``. Providing ``date_of_birth`` narrows
        the results when the defendant's name is common.

        Args:
            first_name (str): The defendant's first name.
            last_name (str): The defendant's last name.
            date_of_birth (datetime.date | None): The defendant's date of birth.
                Optional, but recommended to reduce ambiguous results.

        Returns:
            list[CaseFiling]: All matching ``CaseFiling`` instances, or an empty list
                if none are found.

        Raises:
            EmptyFieldError: If ``first_name`` or ``last_name`` is empty.
            httpx.HTTPStatusError: If the server returns an unsuccessful HTTP status code.
            InvalidResponseError: If the response body is missing the expected results table.

        """
        if not first_name:
            raise EmptyFieldError("first_name")
        if not last_name:
            raise EmptyFieldError("last_name")

        if date_of_birth is not None:
            if isinstance(date_of_birth, str):
                date_of_birth: datetime.date = date_parser.parse(date_of_birth).date
            date_of_birth = date_of_birth.strftime("%Y-%m-%d")

        body = {
            "SearchBy": str(SearchBy.PARTICIPANT_NAME),
            "ParticipantFirstName": first_name,
            "ParticipantLastName": last_name,
            "ParticipantDateOfBirth": date_of_birth,
            "DocketType": "Criminal",
            "__RequestVerificationToken": Constant.CASE_SEARCH_TOKEN,
        }

        html_str = cls._fetch(body)
        return cls._extract_case_filings(html_str)
