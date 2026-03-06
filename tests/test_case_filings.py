from __future__ import annotations

import datetime
from typing import Any
from unittest.mock import patch

import pytest
from justhtml import JustHTML
from pydantic import ValidationError

from pa_record_retriever.case_filings import (
    CaseFiling,
    CaseSearchRequestHeaders,
    DnhMissingError,
    EmptyFieldError,
)
from pa_record_retriever.models import (
    Constant,
    CourtType,
    DocketType,
)
from pa_record_retriever.requests import ContentType, InvalidPageContentError

# ---------------------------------------------------------------------------
# HTML fixtures
# ---------------------------------------------------------------------------

_TABLE_ID = Constant.CASE_SEARCH_RESULTS_TABLE_ID

_HEADERS = [
    "DocketNumber",
    "FilingDate",
    "ShortCaption",
    "PrimaryParticipantName",
    "PrimaryParticipantDOB",
    "CountyName",
    "CaseStatus",
    "OTN",
    "CourtOffice",
    "ComplaintNumber",
    "IncidentNumber",
    "CourtSystem",
]

_DNH_DOCKET_URL = "/Report/CpDocketSheet?docketNumber=CP-51-CR-0001234-2020&dnh=abc123"
_DNH_SUMMARY_URL = "/Report/CpCourtSummary?docketNumber=CP-51-CR-0001234-2020&dnh=abc123"


def _build_table_html(rows_html: str, *, no_results: bool = False) -> str:
    """Returns a minimal HTML page wrapping a ``caseSearchResultGrid`` table."""
    header_ths = "".join(f'<th data-aopc-headername="{h}">{h}</th>' for h in _HEADERS)
    body_content = "<tr><td colspan='12'>No Results Found.</td></tr>" if no_results else rows_html
    return f"""
    <html><body>
    <table id="{_TABLE_ID}">
      <thead><tr>{header_ths}<th></th><th></th></tr></thead>
      <tbody>{body_content}</tbody>
    </table>
    </body></html>
    """


_VALID_ROW_HTML = (
    "<tr>"
    "<td>CP-51-CR-0001234-2020</td>"
    "<td>01/15/2020</td>"
    "<td>Comm. vs. Smith, John</td>"
    "<td>Smith, John</td>"
    "<td>01/01/1980</td>"
    "<td>Philadelphia</td>"
    "<td>Active</td>"
    "<td>T12345678</td>"
    "<td>Philadelphia CCP</td>"
    "<td></td>"
    "<td></td>"
    "<td>Common Pleas</td>"
    f'<td><a href="{_DNH_DOCKET_URL}"><img src="d.png"/></a></td>'
    f'<td><a href="{_DNH_SUMMARY_URL}"><img src="s.png"/></a></td>'
    "</tr>"
)

_VALID_TABLE_HTML = _build_table_html(_VALID_ROW_HTML)
_NO_RESULTS_TABLE_HTML = _build_table_html("", no_results=True)
_MISSING_TABLE_HTML = "<html><body><p>Nothing here.</p></body></html>"


# ---------------------------------------------------------------------------
# EmptyFieldError
# ---------------------------------------------------------------------------


class TestEmptyFieldError:
    """Tests for the ``EmptyFieldError`` exception class."""

    def test_is_value_error_subclass(self) -> None:
        """``EmptyFieldError`` is a subclass of ``ValueError``."""
        assert issubclass(EmptyFieldError, ValueError)

    def test_message_includes_field_name(self) -> None:
        """The error message mentions the field name."""
        err = EmptyFieldError("first_name")
        assert "first_name" in str(err)

    def test_message_format(self) -> None:
        """The error message follows the ``'{field!r} must not be empty.'`` format."""
        err = EmptyFieldError("last_name")
        assert str(err) == "'last_name' must not be empty."


# ---------------------------------------------------------------------------
# DnhMissingError
# ---------------------------------------------------------------------------


class TestDnhMissingError:
    """Tests for the ``DnhMissingError`` exception class."""

    def test_is_value_error_subclass(self) -> None:
        """``DnhMissingError`` is a subclass of ``ValueError``."""
        assert issubclass(DnhMissingError, ValueError)

    def test_message_mentions_dnh(self) -> None:
        """The error message references ``'dnh'``."""
        err = DnhMissingError()
        assert "dnh" in str(err)

    def test_message_attribute(self) -> None:
        """The ``message`` attribute stores the same text as ``str(err)``."""
        err = DnhMissingError()
        assert err.message in str(err)


# ---------------------------------------------------------------------------
# CaseSearchRequestHeaders
# ---------------------------------------------------------------------------


class TestCaseSearchRequestHeaders:
    """Tests for the ``CaseSearchRequestHeaders`` model."""

    def test_content_type_is_form_urlencoded(self) -> None:
        """``content_type`` defaults to ``FORM_URLENCODED``."""
        headers = CaseSearchRequestHeaders()
        assert headers.content_type == ContentType.FORM_URLENCODED

    def test_referer_includes_case_search_endpoint(self) -> None:
        """``referer`` points to the case search endpoint."""
        headers = CaseSearchRequestHeaders()
        assert "/CaseSearch" in headers.referer

    def test_cookie_is_set(self) -> None:
        """``cookie`` is a non-empty string."""
        headers = CaseSearchRequestHeaders()
        assert isinstance(headers.cookie, str)
        assert headers.cookie


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REQUIRED_CASE_FIELDS: dict[str, Any] = {
    "DocketNumber": "CP-51-CR-0001234-2020",
    "FilingDate": datetime.date(2020, 1, 15),
    "ShortCaption": None,
    "PrimaryParticipantName": None,
    "PrimaryParticipantDOB": None,
    "CourtOffice": None,
    "ComplaintNumber": None,
    "IncidentNumber": None,
}


def _make_filing(**overrides: Any) -> CaseFiling:
    """Returns a minimally valid ``CaseFiling``, with fields overridden as specified."""
    return CaseFiling(**{**_REQUIRED_CASE_FIELDS, **overrides})


# ---------------------------------------------------------------------------
# CaseFiling model validators
# ---------------------------------------------------------------------------


class TestCaseFilingParseDateFromString:
    """Tests for ``CaseFiling.parse_date_from_string``."""

    def test_string_date_is_parsed(self) -> None:
        """A string ``filing_date`` is parsed into a ``datetime.date``."""
        case = _make_filing(FilingDate="01/15/2020")
        assert case.filing_date == datetime.date(2020, 1, 15)

    def test_date_object_passes_through(self) -> None:
        """A ``datetime.date`` ``filing_date`` is not altered."""
        d: datetime.date = datetime.date(2020, 1, 15)
        case = _make_filing(FilingDate=d)
        assert case.filing_date == d

    def test_dob_string_is_parsed(self) -> None:
        """A string ``defendant_date_of_birth`` is parsed into a ``datetime.date``."""
        case = _make_filing(PrimaryParticipantDOB="01/01/1980")
        assert case.defendant_date_of_birth == datetime.date(1980, 1, 1)

    def test_none_dob_stays_none(self) -> None:
        """``None`` for ``defendant_date_of_birth`` is not altered."""
        case = _make_filing(PrimaryParticipantDOB=None)
        assert case.defendant_date_of_birth is None


class TestCaseFilingValidateDnhParam:
    """Tests for ``CaseFiling.validate_dnh_param``."""

    def test_none_url_is_accepted(self) -> None:
        """A ``None`` URL does not raise."""
        case = _make_filing(docket_sheet_url=None)
        assert case.docket_sheet_url is None

    def test_url_with_dnh_is_accepted(self) -> None:
        """A URL containing a populated ``dnh`` param is accepted."""
        case = _make_filing(docket_sheet_url=_DNH_DOCKET_URL)
        assert case.docket_sheet_url == _DNH_DOCKET_URL

    def test_url_without_dnh_raises(self) -> None:
        """A URL without a ``dnh`` query param raises a ``ValidationError``."""
        with pytest.raises(ValidationError, match="dnh"):
            _make_filing(docket_sheet_url="/Report/CpDocketSheet?docketNumber=CP-51-CR-0001234-2020")

    def test_url_with_empty_dnh_raises(self) -> None:
        """A URL with an empty ``dnh`` value raises a ``ValidationError``."""
        with pytest.raises(ValidationError):
            _make_filing(docket_sheet_url="/Report/CpDocketSheet?docketNumber=CP-51-CR-0001234-2020&dnh=")

    def test_court_summary_url_also_validated(self) -> None:
        """``court_summary_url`` is subject to the same ``dnh`` validation."""
        with pytest.raises(ValidationError):
            _make_filing(court_summary_url="/Report/CpCourtSummary?docketNumber=CP-51-CR-0001234-2020")


# ---------------------------------------------------------------------------
# CaseFiling._has_records
# ---------------------------------------------------------------------------


class TestHasRecords:
    """Tests for ``CaseFiling._has_records``."""

    def test_returns_true_when_records_present(self) -> None:
        """Returns ``True`` when the table contains row data."""
        page = JustHTML(_VALID_TABLE_HTML, sanitize=False)
        assert CaseFiling._has_records(page) is True

    def test_returns_false_when_no_results(self) -> None:
        """Returns ``False`` when the table contains a 'no results' message."""
        page = JustHTML(_NO_RESULTS_TABLE_HTML, sanitize=False)
        assert CaseFiling._has_records(page) is False

    def test_raises_when_table_missing(self) -> None:
        """Raises ``InvalidPageContentError`` when the results table is absent."""
        page = JustHTML(_MISSING_TABLE_HTML, sanitize=False)
        with pytest.raises(InvalidPageContentError):
            CaseFiling._has_records(page)


# ---------------------------------------------------------------------------
# CaseFiling._get_table_headers
# ---------------------------------------------------------------------------


class TestGetTableHeaders:
    """Tests for ``CaseFiling._get_table_headers``."""

    def test_returns_header_names(self) -> None:
        """Returns the list of ``data-aopc-headername`` values."""
        page = JustHTML(_VALID_TABLE_HTML, sanitize=False)
        from pa_record_retriever.models import Constant as _C

        table = page.query_one(f"table#{_C.CASE_SEARCH_RESULTS_TABLE_ID}")
        headers = CaseFiling._get_table_headers(table)
        assert "DocketNumber" in headers
        assert "FilingDate" in headers

    def test_raises_when_no_th_elements(self) -> None:
        """Raises ``InvalidPageContentError`` when the table has no ``<th>``
        elements."""
        html = f'<html><body><table id="{_TABLE_ID}"><tbody><tr><td>data</td></tr></tbody></table></body></html>'
        page = JustHTML(html, sanitize=False)
        table = page.query_one(f"table#{_TABLE_ID}")
        with pytest.raises(InvalidPageContentError):
            CaseFiling._get_table_headers(table)

    def test_excludes_th_without_attribute(self) -> None:
        """``<th>`` elements without ``data-aopc-headername`` are excluded."""
        page = JustHTML(_VALID_TABLE_HTML, sanitize=False)
        table = page.query_one(f"table#{_TABLE_ID}")
        headers = CaseFiling._get_table_headers(table)
        # The fixture has two extra ths without the attribute (for URL columns)
        assert len(headers) == len(_HEADERS)


# ---------------------------------------------------------------------------
# CaseFiling._get_records
# ---------------------------------------------------------------------------


class TestGetRecords:
    """Tests for ``CaseFiling._get_records``."""

    def test_returns_list_of_case_filings(self) -> None:
        """A valid page returns a non-empty list of ``CaseFiling`` instances."""
        page = JustHTML(_VALID_TABLE_HTML, sanitize=False)
        results = CaseFiling._get_records(page)
        assert len(results) == 1
        assert isinstance(results[0], CaseFiling)

    def test_docket_number_populated(self) -> None:
        """The ``docket_number`` field is correctly extracted from the row."""
        page = JustHTML(_VALID_TABLE_HTML, sanitize=False)
        result = CaseFiling._get_records(page)[0]
        assert result.docket_number == "CP-51-CR-0001234-2020"

    def test_filing_date_populated(self) -> None:
        """The ``filing_date`` field is parsed from the row."""
        page = JustHTML(_VALID_TABLE_HTML, sanitize=False)
        result = CaseFiling._get_records(page)[0]
        assert result.filing_date == datetime.date(2020, 1, 15)

    def test_docket_sheet_url_extracted(self) -> None:
        """The ``docket_sheet_url`` is extracted from the ``DocketSheet`` link."""
        page = JustHTML(_VALID_TABLE_HTML, sanitize=False)
        result = CaseFiling._get_records(page)[0]
        assert result.docket_sheet_url == _DNH_DOCKET_URL

    def test_court_summary_url_extracted(self) -> None:
        """The ``court_summary_url`` is extracted from the ``CourtSummary`` link."""
        page = JustHTML(_VALID_TABLE_HTML, sanitize=False)
        result = CaseFiling._get_records(page)[0]
        assert result.court_summary_url == _DNH_SUMMARY_URL

    def test_court_type_imputed_from_docket_number(self) -> None:
        """``court_type`` is imputed from the docket number prefix."""
        page = JustHTML(_VALID_TABLE_HTML, sanitize=False)
        result = CaseFiling._get_records(page)[0]
        assert result.court_type == CourtType.COMMON_PLEAS

    def test_docket_type_imputed_from_docket_number(self) -> None:
        """``docket_type`` is imputed from the docket number segment."""
        page = JustHTML(_VALID_TABLE_HTML, sanitize=False)
        result = CaseFiling._get_records(page)[0]
        assert result.docket_type == DocketType.CRIMINAL

    def test_duplicate_docket_numbers_deduplicated(self) -> None:
        """Rows with the same docket number are deduplicated."""
        double_row_html = _VALID_ROW_HTML + _VALID_ROW_HTML
        html = _build_table_html(double_row_html)
        page = JustHTML(html, sanitize=False)
        results = CaseFiling._get_records(page)
        assert len(results) == 1

    def test_empty_cell_becomes_none(self) -> None:
        """An empty ``<td>`` cell is converted to ``None``."""
        page = JustHTML(_VALID_TABLE_HTML, sanitize=False)
        result = CaseFiling._get_records(page)[0]
        assert result.complaint_number is None


# ---------------------------------------------------------------------------
# CaseFiling._extract_case_filings
# ---------------------------------------------------------------------------


class TestExtractCaseFilings:
    """Tests for ``CaseFiling._extract_case_filings``."""

    def test_returns_filings_from_valid_html(self) -> None:
        """A valid HTML string with records returns a list of ``CaseFiling`` objects."""
        results = CaseFiling._extract_case_filings(_VALID_TABLE_HTML)
        assert len(results) == 1

    def test_returns_empty_list_when_no_results(self) -> None:
        """An HTML page with a no-results table returns an empty list."""
        results = CaseFiling._extract_case_filings(_NO_RESULTS_TABLE_HTML)
        assert results == []

    def test_raises_when_table_missing(self) -> None:
        """An HTML page without the results table raises ``InvalidPageContentError``."""
        with pytest.raises(InvalidPageContentError):
            CaseFiling._extract_case_filings(_MISSING_TABLE_HTML)


# ---------------------------------------------------------------------------
# CaseFiling._raise_for_invalid_content
# ---------------------------------------------------------------------------


class TestRaiseForInvalidContent:
    """Tests for ``CaseFiling._raise_for_invalid_content``."""

    def test_valid_html_does_not_raise(self) -> None:
        """HTML containing the expected table ID does not raise."""
        CaseFiling._raise_for_invalid_content(_VALID_TABLE_HTML)

    def test_non_string_raises_invalid_response_error(self) -> None:
        """A non-string input raises ``InvalidResponseError``."""
        from pa_record_retriever.requests import InvalidResponseError

        with pytest.raises(InvalidResponseError):
            CaseFiling._raise_for_invalid_content(b"not a string")  # type: ignore[arg-type]

    def test_missing_table_id_raises(self) -> None:
        """HTML missing the results table ID raises ``InvalidResponseError``."""
        from pa_record_retriever.requests import InvalidResponseError

        with pytest.raises(InvalidResponseError):
            CaseFiling._raise_for_invalid_content("<html><body>nothing</body></html>")

    def test_narrow_search_warning_logged(self) -> None:
        """A page containing 'please narrow your search' emits a warning log."""
        html_with_narrow = f'<table id="{_TABLE_ID}">please narrow your search</table>'
        with patch("pa_record_retriever.case_filings.logger") as mock_logger:
            CaseFiling._raise_for_invalid_content(html_with_narrow)
            mock_logger.warning.assert_called_once()


# ---------------------------------------------------------------------------
# CaseFiling.from_docket_number
# ---------------------------------------------------------------------------


class TestFromDocketNumber:
    """Tests for ``CaseFiling.from_docket_number``."""

    def test_empty_docket_number_raises(self) -> None:
        """An empty ``docket_number`` raises ``EmptyFieldError``."""
        with pytest.raises(EmptyFieldError):
            CaseFiling.from_docket_number("")

    def test_returns_none_when_no_results(self) -> None:
        """Returns ``None`` when no filings are found."""
        with patch.object(CaseFiling, "_fetch", return_value=_NO_RESULTS_TABLE_HTML):
            result = CaseFiling.from_docket_number("CP-51-CR-0001234-2020")
        assert result is None

    def test_returns_case_filing_on_match(self) -> None:
        """Returns the first ``CaseFiling`` when results are found."""
        with patch.object(CaseFiling, "_fetch", return_value=_VALID_TABLE_HTML):
            result = CaseFiling.from_docket_number("CP-51-CR-0001234-2020")
        assert isinstance(result, CaseFiling)
        assert result.docket_number == "CP-51-CR-0001234-2020"


# ---------------------------------------------------------------------------
# CaseFiling.from_defendant
# ---------------------------------------------------------------------------


class TestFromDefendant:
    """Tests for ``CaseFiling.from_defendant``."""

    def test_empty_first_name_raises(self) -> None:
        """An empty ``first_name`` raises ``EmptyFieldError``."""
        with pytest.raises(EmptyFieldError):
            CaseFiling.from_defendant("", "Smith")

    def test_empty_last_name_raises(self) -> None:
        """An empty ``last_name`` raises ``EmptyFieldError``."""
        with pytest.raises(EmptyFieldError):
            CaseFiling.from_defendant("John", "")

    def test_returns_list_of_case_filings(self) -> None:
        """Returns a list of ``CaseFiling`` instances on success."""
        with patch.object(CaseFiling, "_fetch", return_value=_VALID_TABLE_HTML):
            results = CaseFiling.from_defendant("John", "Smith")
        assert isinstance(results, list)
        assert len(results) == 1

    def test_returns_empty_list_when_no_results(self) -> None:
        """Returns an empty list when no filings are found."""
        with patch.object(CaseFiling, "_fetch", return_value=_NO_RESULTS_TABLE_HTML):
            results = CaseFiling.from_defendant("John", "Smith")
        assert results == []

    def test_date_object_passed_directly(self) -> None:
        """A ``datetime.date`` dob is formatted as ``%Y-%m-%d`` in the request body."""
        captured_bodies: list[dict[str, Any]] = []

        def capture_fetch(body: dict[str, Any]) -> str:
            """Records the request body and returns no-results HTML."""
            captured_bodies.append(body)
            return _NO_RESULTS_TABLE_HTML

        dob: datetime.date = datetime.date(1980, 6, 15)
        with patch.object(CaseFiling, "_fetch", side_effect=capture_fetch):
            CaseFiling.from_defendant("John", "Smith", date_of_birth=dob)

        assert captured_bodies[0]["ParticipantDateOfBirth"] == "1980-06-15"

    def test_none_dob_passes_none_in_body(self) -> None:
        """When ``date_of_birth`` is ``None``, ``ParticipantDateOfBirth`` is
        ``None``."""
        captured_bodies: list[dict[str, Any]] = []

        def capture_fetch(body: dict[str, Any]) -> str:
            """Records the request body and returns no-results HTML."""
            captured_bodies.append(body)
            return _NO_RESULTS_TABLE_HTML

        with patch.object(CaseFiling, "_fetch", side_effect=capture_fetch):
            CaseFiling.from_defendant("John", "Smith", date_of_birth=None)

        assert captured_bodies[0]["ParticipantDateOfBirth"] is None
