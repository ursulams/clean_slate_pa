from __future__ import annotations

import datetime
from unittest.mock import MagicMock, patch

import httpx
import pytest

from pa_record_retriever.court_summaries import (
    Case,
    Charge,
    CourtSummary,
    InvalidQueryStringError,
    NoCourtSummaryUrlError,
    NoFilingsFoundError,
    SealedCaseError,
    Sentence,
)
from pa_record_retriever.models import County, CourtType, DocketType
from pa_record_retriever.pypdf.enum import DelimiterGlyph, FontWeight
from pa_record_retriever.requests import InvalidResponseError

_EO = DelimiterGlyph.END_OBJECT  # "\n"
_R = DelimiterGlyph.RETURN  # "↩"
_AO = DelimiterGlyph.ATTRIBUTES_OPEN  # "《"
_AC = DelimiterGlyph.ATTRIBUTES_CLOSE  # "》"
_B = FontWeight.BOLD  # "bold"

_STATUS_ATTRS = f"{_AO}040|050|060|{_B}{_AC}"
_DOCKET_ATTRS = f"{_AO}060|080|100|{_B}{_AC}"


class TestSealedCaseError:
    """Tests for the ``SealedCaseError`` exception class."""

    def test_is_exception_subclass(self) -> None:
        """``SealedCaseError`` is a subclass of ``Exception``."""
        assert issubclass(SealedCaseError, Exception)

    def test_message_mentions_sealed(self) -> None:
        """The default message mentions the sealed state."""
        err = SealedCaseError()
        assert "sealed" in str(err).lower()


class TestInvalidQueryStringError:
    """Tests for the ``InvalidQueryStringError`` exception class."""

    def test_is_exception_subclass(self) -> None:
        """``InvalidQueryStringError`` is a subclass of ``Exception``."""
        assert issubclass(InvalidQueryStringError, Exception)

    def test_message_includes_query_string(self) -> None:
        """The error message includes the offending query string."""
        err = InvalidQueryStringError("/Report/Unknown?x=1")
        assert "/Report/Unknown?x=1" in str(err)


class TestNoFilingsFoundError:
    """Tests for the ``NoFilingsFoundError`` exception class."""

    def test_message_includes_docket_number(self) -> None:
        """The error message includes the docket number."""
        err = NoFilingsFoundError("CP-51-CR-0001234-2020")
        assert "CP-51-CR-0001234-2020" in str(err)


class TestNoCourtSummaryUrlError:
    """Tests for the ``NoCourtSummaryUrlError`` exception class."""

    def test_message_includes_docket_number(self) -> None:
        """The error message includes the docket number."""
        err = NoCourtSummaryUrlError("CP-51-CR-0001234-2020")
        assert "CP-51-CR-0001234-2020" in str(err)


class TestSentence:
    """Tests for the ``Sentence`` Pydantic model."""

    def test_required_fields_populated(self) -> None:
        """A ``Sentence`` can be constructed with the required fields."""
        sentence = Sentence(
            sentence_date=datetime.date(2021, 3, 10),
            sentence_type="Probation",
        )
        assert sentence.sentence_date == datetime.date(2021, 3, 10)
        assert sentence.sentence_type == "Probation"

    def test_optional_fields_default_to_none(self) -> None:
        """``program_period`` and ``sentence_length`` default to ``None``."""
        sentence = Sentence(
            sentence_date=datetime.date(2021, 3, 10),
            sentence_type="Probation",
        )
        assert sentence.program_period is None
        assert sentence.sentence_length is None

    def test_program_type_alias_accepted(self) -> None:
        """``sentence_type`` can be set via the ``program_type`` alias."""
        sentence = Sentence(
            sentence_date=datetime.date(2021, 3, 10),
            program_type="Incarceration",
        )
        assert sentence.sentence_type == "Incarceration"


class TestCharge:
    """Tests for the ``Charge`` Pydantic model."""

    def test_required_field_populated(self) -> None:
        """A ``Charge`` can be constructed with only ``charge_description``."""
        charge = Charge(charge_description="Theft")
        assert charge.charge_description == "Theft"

    def test_optional_fields_default_to_none(self) -> None:
        """Optional fields default to ``None``."""
        charge = Charge(charge_description="Theft")
        assert charge.sequence_number is None
        assert charge.statute is None
        assert charge.grade is None
        assert charge.disposition is None
        assert charge.counts is None

    def test_sentences_default_to_empty_list(self) -> None:
        """``sentences`` defaults to an empty list."""
        charge = Charge(charge_description="Theft")
        assert charge.sentences == []

    def test_sentence_alias_accepted(self) -> None:
        """``sentences`` can be populated via the ``sentence`` alias."""
        sentence_data = {
            "sentence_date": datetime.date(2021, 3, 10),
            "sentence_type": "Probation",
        }
        charge = Charge(charge_description="Theft", sentence=[sentence_data])
        assert len(charge.sentences) == 1
        assert isinstance(charge.sentences[0], Sentence)


class TestCase:
    """Tests for the ``Case`` Pydantic model."""

    class TestFillMissingValuesFromDocketNumber:
        """Tests for the ``fill_missing_values_from_docket_number`` validator."""

        def test_court_type_inferred_from_docket_number(self) -> None:
            """``court_type`` is inferred from a ``CP-`` docket number."""
            case = Case(docket_number="CP-51-CR-0001234-2020")
            assert case.court_type == CourtType.COMMON_PLEAS

        def test_docket_type_inferred_from_docket_number(self) -> None:
            """``docket_type`` is inferred from the ``-CR-`` segment."""
            case = Case(docket_number="CP-51-CR-0001234-2020")
            assert case.docket_type == DocketType.CRIMINAL

        def test_county_inferred_from_cp_docket_number(self) -> None:
            """``county`` is inferred from the county code in a ``CP-`` docket."""
            case = Case(docket_number="CP-51-CR-0001234-2020")
            assert case.county == County.PHILADELPHIA

        def test_existing_court_type_not_overwritten(self) -> None:
            """A pre-supplied ``court_type`` is not overwritten."""
            case = Case(docket_number="CP-51-CR-0001234-2020", CourtSystem="Municipal Court")
            assert case.court_type == CourtType.MUNICIPAL_COURT

        def test_existing_county_not_overwritten(self) -> None:
            """A pre-supplied ``county`` is not overwritten."""
            case = Case(docket_number="CP-51-CR-0001234-2020", CountyName="Adams")
            assert case.county == County.ADAMS

        def test_mj_docket_number(self) -> None:
            """An ``MJ-`` docket is handled correctly."""
            case = Case(docket_number="MJ-01-CR-0001234-2020")
            assert case.court_type == CourtType.MAGISTERIAL_DISTRICT
            assert case.county == County.PHILADELPHIA

    def test_optional_fields_default_to_none(self) -> None:
        """All optional fields default to ``None``."""
        case = Case(docket_number="CP-51-CR-0001234-2020")
        assert case.judge is None
        assert case.defense_attorney is None
        assert case.arrest_date is None
        assert case.bail_type is None

    def test_charges_default_to_empty_list(self) -> None:
        """``charges`` defaults to an empty list."""
        case = Case(docket_number="CP-51-CR-0001234-2020")
        assert case.charges == []


class TestRemoveFooters:
    """Tests for ``CourtSummary._remove_footers``."""

    def test_no_footer_text_unchanged(self) -> None:
        """Text without footer blocks is returned unchanged."""
        text = f"Active{_STATUS_ATTRS}{_EO}CP-51-CR-0001234-2020{_DOCKET_ATTRS}{_EO}"
        result = CourtSummary._remove_footers(text)
        assert result == text

    def test_mdjs_footer_at_end_of_text_removed(self) -> None:
        """A trailing ``MDJS...Printed:`` block is replaced with a newline."""
        # The second re.sub in _remove_footers: (?<=\n)MDJS.*\nPrinted:(.*\n){,5}$
        text = "content\nMDJS 2.0\nPrinted: 03/01/2025\nPage 1 of 2\n"
        result = CourtSummary._remove_footers(text)
        assert "MDJS" not in result
        assert "Printed: 03/01/2025" not in result
        assert "content" in result

    def test_printed_continued_bold_block_removed(self) -> None:
        """A ``Printed:...(Continued)`` followed by a bold attribute block is
        stripped."""
        # Third re.sub: Printed:(.*\n){,10}.*\(Continued\)(↩|.*bold》)
        block = f"Printed: 03/01/2025\nPage 1 of 2\n(Continued){_R}"
        text = f"before\n{block}after"
        result = CourtSummary._remove_footers(text)
        assert "(Continued)" not in result

    def test_recent_entries_block_removed(self) -> None:
        """A ``Printed:...Recent entries made in the court filing`` block is
        stripped."""
        # Fourth re.sub: Printed:(.*\n){,3}Recent entries made in the court filing.*\n
        block = "Printed: 03/01/2025\nRecent entries made in the court filing offices of Pennsylvania\n"
        text = f"before\n{block}after"
        result = CourtSummary._remove_footers(text)
        assert "Recent entries" not in result


class TestHandleStatusLine:
    """Tests for ``CourtSummary._handle_status_line``."""

    def test_simple_line_no_return_appended_unchanged(self) -> None:
        """A status line without a ``RETURN`` is appended unchanged."""
        line = f"Active{_STATUS_ATTRS}"
        output: list[str] = []
        new_status, new_county = CourtSummary._handle_status_line(
            line, current_status="", current_county="", output_lines=output
        )
        assert output == [line]
        assert new_status == line

    def test_aliases_line_appended_unchanged(self) -> None:
        """A line containing ``'Aliases:'`` is appended unchanged even with RETURN."""
        line = f"Aliases: Smith, Johnny{_R}{_STATUS_ATTRS}"
        output: list[str] = []
        CourtSummary._handle_status_line(line, current_status="", current_county="", output_lines=output)
        assert output == [line]

    def test_county_extracted_from_single_return(self) -> None:
        """With one embedded RETURN, the county before the RETURN is extracted."""
        county = "Philadelphia"
        status = f"Active{_STATUS_ATTRS}"
        line = f"{county}{_R}{status}"
        output: list[str] = []
        new_status, new_county = CourtSummary._handle_status_line(
            line, current_status="Active", current_county="", output_lines=output
        )
        assert new_county == county
        assert _B in new_status

    def test_subject_name_extracted_when_initial_status_empty(self) -> None:
        """With empty ``current_status``, the subject name is split off and appended."""
        subject = "Smith, John"
        county = "Philadelphia"
        status = f"Active{_STATUS_ATTRS}"
        line = f"{subject}{_R}{county}{_R}{status}"
        output: list[str] = []
        CourtSummary._handle_status_line(line, current_status="", current_county="", output_lines=output)
        # Subject name line should be in output
        assert any(subject in o for o in output)


class TestHandleDocketNumberLine:
    """Tests for ``CourtSummary._handle_docket_number_line``."""

    def test_new_case_appended_to_output(self) -> None:
        """A new docket number line is appended to output (possibly with county
        prepended)."""
        line = f"CP-51-CR-0001234-2020{_DOCKET_ATTRS}"
        status = f"Active{_STATUS_ATTRS}"
        output: list[str] = [status]
        CourtSummary._handle_docket_number_line(
            line, current_status=status, current_case=[], current_county="Philadelphia", output_lines=output
        )
        assert any("CP-51-CR-0001234-2020" in o for o in output)

    def test_duplicate_docket_number_ignored(self) -> None:
        """A docket number already in ``current_case`` is not re-appended."""
        line = f"CP-51-CR-0001234-2020{_DOCKET_ATTRS}"
        status = f"Active{_STATUS_ATTRS}"
        output: list[str] = [status, line]
        new_county, new_case = CourtSummary._handle_docket_number_line(
            line, current_status=status, current_case=[line], current_county="Philadelphia", output_lines=output
        )
        # No new entry added
        assert output.count(line) == 1

    def test_current_case_reset_on_new_docket(self) -> None:
        """``current_case`` is reset to a fresh list when a new docket is
        encountered."""
        line = f"CP-51-CR-0005678-2021{_DOCKET_ATTRS}"
        prev_line = f"CP-51-CR-0001234-2020{_DOCKET_ATTRS}"
        status = f"Active{_STATUS_ATTRS}"
        output: list[str] = [status, prev_line]
        _, new_case = CourtSummary._handle_docket_number_line(
            line, current_status=status, current_case=[prev_line], current_county="Philadelphia", output_lines=output
        )
        assert any("CP-51-CR-0005678-2021" in c for c in new_case)
        assert all("CP-51-CR-0001234-2020" not in c for c in new_case)

    def test_county_extracted_from_single_return(self) -> None:
        """With one embedded RETURN, the text before RETURN is used as county."""
        county = "Philadelphia"
        docket = f"CP-51-CR-0001234-2020{_DOCKET_ATTRS}"
        line = f"{county}{_R}{docket}"
        status = f"Active{_STATUS_ATTRS}"
        output: list[str] = [status]
        new_county, _ = CourtSummary._handle_docket_number_line(
            line, current_status=status, current_case=[], current_county="", output_lines=output
        )
        assert new_county == county


class TestIsDuplicateCaseLine:
    """Tests for ``CourtSummary._is_duplicate_case_line``."""

    def test_returns_false_when_line_not_in_case(self) -> None:
        """Returns ``False`` when the line has not been seen before."""
        line = f"OTN: T12345678{_AO}030|040|050|{_B}{_AC}"
        assert CourtSummary._is_duplicate_case_line(line, []) is False

    def test_returns_false_when_line_in_case_but_not_bold_or_header(self) -> None:
        """Returns ``False`` for a plain line already in case that is not bold or a
        header."""
        line = "Some random text"
        assert CourtSummary._is_duplicate_case_line(line, [line]) is False

    def test_returns_true_for_bold_duplicate(self) -> None:
        """Returns ``True`` when the line is in ``current_case`` and ends with bold
        attribute."""
        line = f"Closed{_AO}030|040|050|{_B}{_AC}"
        assert CourtSummary._is_duplicate_case_line(line, [line]) is True

    def test_returns_true_for_charge_header_duplicate(self) -> None:
        """Returns ``True`` when the line starts with a charge header and is already in
        case."""
        line = "OTN: T12345678"
        assert CourtSummary._is_duplicate_case_line(line, [line]) is True

    def test_arrest_date_header_recognized(self) -> None:
        """An ``Arrest Dt:`` prefix is recognized as a charge header."""
        line = "Arrest Dt: 01/01/2020"
        assert CourtSummary._is_duplicate_case_line(line, [line]) is True


class TestPreprocess:
    """Tests for ``CourtSummary._preprocess``."""

    def test_empty_lines_skipped(self) -> None:
        """Lines that are empty or whitespace-only are not included in output."""
        text = f"{_EO}   {_EO}{_EO}"
        result = CourtSummary._preprocess(text)
        # All whitespace lines are dropped; only the trailing END_OBJECT remains
        assert result.strip() == ""

    def test_statewide_lines_skipped(self) -> None:
        """Lines starting with ``'Statewide'`` are dropped."""
        text = f"Statewide Criminal History{_EO}Normal line{_EO}"
        result = CourtSummary._preprocess(text)
        assert "Statewide" not in result
        assert "Normal line" in result

    def test_status_line_processed(self) -> None:
        """A status line is processed and appears in the output."""
        status_line = f"Active{_STATUS_ATTRS}"
        text = f"{status_line}{_EO}"
        result = CourtSummary._preprocess(text)
        assert "Active" in result

    def test_output_ends_with_end_object(self) -> None:
        """The output always ends with the ``END_OBJECT`` delimiter."""
        text = f"Active{_STATUS_ATTRS}{_EO}"
        result = CourtSummary._preprocess(text)
        assert result.endswith(_EO)

    def test_non_case_lines_pass_through(self) -> None:
        """Lines outside a case context are passed through to the output."""
        line = "Smith, John"
        text = f"{line}{_EO}"
        result = CourtSummary._preprocess(text)
        assert line in result

    def test_duplicate_case_lines_suppressed(self) -> None:
        """Duplicate charge-header lines within the same case are suppressed."""
        status = f"Active{_STATUS_ATTRS}"
        docket = f"CP-51-CR-0001234-2020{_DOCKET_ATTRS}"
        otn_line = "OTN: T12345678"
        # Same line appears twice after the docket number
        text = f"{status}{_EO}{docket}{_EO}{otn_line}{_EO}{otn_line}{_EO}"
        result = CourtSummary._preprocess(text)
        assert result.count(otn_line) == 1


class TestRaiseForStatus:
    """Tests for ``CourtSummary._raise_for_status``."""

    def test_raises_sealed_case_error_on_no_data_found(self) -> None:
        """Raises ``SealedCaseError`` when the response text contains 'no data
        found'."""
        mock_response: MagicMock = MagicMock(spec=httpx.Response)
        mock_response.text = "No data found for the report."
        with pytest.raises(SealedCaseError):
            CourtSummary._raise_for_status(mock_response)

    def test_calls_raise_for_status_on_success(self) -> None:
        """Calls ``response.raise_for_status()`` when no special message is present."""
        mock_response: MagicMock = MagicMock(spec=httpx.Response)
        mock_response.text = "Normal PDF response"
        CourtSummary._raise_for_status(mock_response)
        mock_response.raise_for_status.assert_called_once()

    def test_case_insensitive_check(self) -> None:
        """The 'no data found' check is case-insensitive."""
        mock_response: MagicMock = MagicMock(spec=httpx.Response)
        mock_response.text = "NO DATA FOUND FOR THE REPORT"
        with pytest.raises(SealedCaseError):
            CourtSummary._raise_for_status(mock_response)


class TestRaiseForInvalidContent:
    """Tests for ``CourtSummary._raise_for_invalid_content``."""

    def test_valid_cpcms_pdf_does_not_raise(self) -> None:
        """Content whose first page contains ``'CPCMS'`` passes validation."""
        mock_reader: MagicMock = MagicMock()
        mock_page: MagicMock = MagicMock()
        mock_page.extract_text.return_value = "CPCMS Court Summary"
        mock_reader.pages = [mock_page]

        with patch("pa_record_retriever.court_summaries.PdfReader", return_value=mock_reader):
            CourtSummary._raise_for_invalid_content(b"fake pdf")

    def test_valid_mdjs_pdf_does_not_raise(self) -> None:
        """Content whose first page contains ``'MDJS'`` passes validation."""
        mock_reader: MagicMock = MagicMock()
        mock_page: MagicMock = MagicMock()
        mock_page.extract_text.return_value = "MDJS Court Summary"
        mock_reader.pages = [mock_page]

        with patch("pa_record_retriever.court_summaries.PdfReader", return_value=mock_reader):
            CourtSummary._raise_for_invalid_content(b"fake pdf")

    def test_empty_pages_raises(self) -> None:
        """A PDF reader with no pages raises ``InvalidResponseError``."""
        mock_reader: MagicMock = MagicMock()
        mock_reader.pages = []

        with (
            patch("pa_record_retriever.court_summaries.PdfReader", return_value=mock_reader),
            pytest.raises(InvalidResponseError),
        ):
            CourtSummary._raise_for_invalid_content(b"fake pdf")

    def test_pdf_read_error_raises_invalid_response(self) -> None:
        """A ``PdfReadError`` is wrapped in ``InvalidResponseError``."""
        from pypdf.errors import PdfReadError

        with (
            patch("pa_record_retriever.court_summaries.PdfReader", side_effect=PdfReadError("corrupt")),
            pytest.raises(InvalidResponseError),
        ):
            CourtSummary._raise_for_invalid_content(b"not a pdf")

    def test_empty_file_error_raises_invalid_response(self) -> None:
        """An ``EmptyFileError`` is wrapped in ``InvalidResponseError``."""
        from pypdf.errors import EmptyFileError

        with (
            patch("pa_record_retriever.court_summaries.PdfReader", side_effect=EmptyFileError()),
            pytest.raises(InvalidResponseError),
        ):
            CourtSummary._raise_for_invalid_content(b"")

    def test_non_court_pdf_raises(self) -> None:
        """A PDF without ``CPCMS``/``MDJS`` but with ``Court Summary`` or ``DOCKET``
        raises."""
        mock_reader: MagicMock = MagicMock()
        mock_page: MagicMock = MagicMock()
        mock_page.extract_text.return_value = "Court Summary Document"
        mock_reader.pages = [mock_page]

        with (
            patch("pa_record_retriever.court_summaries.PdfReader", return_value=mock_reader),
            pytest.raises(InvalidResponseError),
        ):
            CourtSummary._raise_for_invalid_content(b"fake pdf")


class TestFromQueryString:
    """Tests for ``CourtSummary.from_query_string``."""

    def test_invalid_query_string_raises(self) -> None:
        """A query string not matching ``/Cp`` or ``/Mdj`` raises
        ``InvalidQueryStringError``."""
        with pytest.raises(InvalidQueryStringError):
            CourtSummary.from_query_string("/Report/Unknown?dnh=abc123")

    def test_cp_query_string_sets_peg_path(self) -> None:
        """A ``/Cp`` query string sets the PEG path to the Common Pleas grammar."""
        mock_summary: MagicMock = MagicMock(spec=CourtSummary)
        with (
            patch.object(CourtSummary, "_fetch", return_value=b"pdf"),
            patch.object(CourtSummary, "from_bytes", return_value=mock_summary),
        ):
            CourtSummary.from_query_string("/Report/CpCourtSummary?dnh=abc")

        peg_path = CourtSummary._peg_path_ctx.get()
        assert "common_pleas" in str(peg_path)

    def test_mdj_query_string_sets_peg_path(self) -> None:
        """A ``/Mdj`` query string sets the PEG path to the Magisterial District
        grammar."""
        mock_summary: MagicMock = MagicMock(spec=CourtSummary)
        with (
            patch.object(CourtSummary, "_fetch", return_value=b"pdf"),
            patch.object(CourtSummary, "from_bytes", return_value=mock_summary),
        ):
            CourtSummary.from_query_string("/Report/MdjCourtSummary?dnh=abc")

        peg_path = CourtSummary._peg_path_ctx.get()
        assert "magisterial_district" in str(peg_path)

    def test_returns_court_summary_from_from_bytes(self) -> None:
        """The return value is the object produced by ``from_bytes``."""
        mock_summary: MagicMock = MagicMock(spec=CourtSummary)
        with (
            patch.object(CourtSummary, "_fetch", return_value=b"pdf"),
            patch.object(CourtSummary, "from_bytes", return_value=mock_summary),
        ):
            result = CourtSummary.from_query_string("/Report/CpCourtSummary?dnh=abc")

        assert result is mock_summary


class TestFromRelatedDocketNumber:
    """Tests for ``CourtSummary.from_related_docket_number``."""

    def test_raises_when_no_filings_found(self) -> None:
        """Raises ``NoFilingsFoundError`` when ``CaseFiling.from_docket_number`` returns
        ``None``."""
        from pa_record_retriever.case_filings import CaseFiling

        with (
            patch.object(CaseFiling, "from_docket_number", return_value=None),
            pytest.raises(NoFilingsFoundError),
        ):
            CourtSummary.from_related_docket_number("CP-51-CR-0001234-2020")

    def test_raises_when_no_court_summary_url(self) -> None:
        """Raises ``NoCourtSummaryUrlError`` when the filing has no court summary
        URL."""
        from pa_record_retriever.case_filings import CaseFiling

        mock_filing: MagicMock = MagicMock(spec=CaseFiling)
        mock_filing.court_summary_url = None

        with (
            patch.object(CaseFiling, "from_docket_number", return_value=mock_filing),
            pytest.raises(NoCourtSummaryUrlError),
        ):
            CourtSummary.from_related_docket_number("CP-51-CR-0001234-2020")

    def test_delegates_to_from_query_string(self) -> None:
        """Delegates to ``from_query_string`` using the filing's court summary URL."""
        from pa_record_retriever.case_filings import CaseFiling

        summary_url = "/Report/CpCourtSummary?dnh=abc123"
        mock_filing: MagicMock = MagicMock(spec=CaseFiling)
        mock_filing.court_summary_url = summary_url

        mock_summary: MagicMock = MagicMock(spec=CourtSummary)

        with (
            patch.object(CaseFiling, "from_docket_number", return_value=mock_filing),
            patch.object(CourtSummary, "from_query_string", return_value=mock_summary) as mock_fqs,
        ):
            result = CourtSummary.from_related_docket_number("CP-51-CR-0001234-2020")

        mock_fqs.assert_called_once_with(summary_url)
        assert result is mock_summary
