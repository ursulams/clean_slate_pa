from __future__ import annotations

import datetime
import importlib.resources
import io
import os
import re
from contextvars import ContextVar
from pathlib import Path
from typing import ClassVar

import httpx
from loguru import logger
from pydantic import AliasChoices, Field, model_validator
from pypdf import PdfReader
from pypdf.errors import EmptyFileError, PdfReadError

from pa_record_retriever.case_filings import CaseFiling
from pa_record_retriever.models import (
    CaseStatusMixin,
    CaseTypeMixin,
    Constant,
    County,
    CountyMixin,
    CourtRequestHeaders,
    CourtType,
    DocketNumberMixin,
    DocketType,
    OtnMixin,
)
from pa_record_retriever.parsimonious.grammar import Grammar
from pa_record_retriever.parsimonious.models import ParsedDocument
from pa_record_retriever.pydantic import BaseModel
from pa_record_retriever.pypdf.enum import DelimiterGlyph, FontWeight
from pa_record_retriever.requests import InvalidResponseError, retry_x3


class SealedCaseError(Exception):
    """Custom exception raised when a case is sealed (or expunged) and documents can no
    longer be fetched by members of the general public."""

    def __init__(self) -> None:
        super().__init__("HTTP response is 401. Case is presumed sealed.")


class InvalidQueryStringError(Exception):
    """Raised when a query string cannot be mapped to a known court type."""

    def __init__(self, query_string: str) -> None:
        super().__init__(f"Query string does not match a known court type: {query_string!r}")


class NoFilingsFoundError(Exception):
    """Raised when no case filings are found for the given docket number."""

    def __init__(self, docket_number: str) -> None:
        super().__init__(f"No case filings found for docket number: {docket_number!r}")


class NoCourtSummaryUrlError(Exception):
    """Raised when the case filing for a docket number does not have a court summary
    URL."""

    def __init__(self, docket_number: str) -> None:
        super().__init__(f"No court summary URL found for docket number: {docket_number!r}")


class Sentence(BaseModel):
    """Represents the sentence information for a conviction, as presented in the court
    summary document."""

    sentence_date: datetime.date
    """The date of the sentence."""

    sentence_type: str = Field(validation_alias=AliasChoices("program_type", "sentence_type"))
    """The type of sentence (e.g., probation, incarceration)."""

    program_period: str | None = None
    """
    The period of the program associated with the sentence.

    When the sentence is confinement, this is the minimum sentence length.

    """

    sentence_length: str | None = None
    """The length of the sentence."""


class Charge(BaseModel):
    """Represents a charge, as presented in the court summary document."""

    sequence_number: int | None = None
    """The sequence number of the charge, scoped to the case."""

    statute: str | None = None
    """The statute under which the charge is filed."""

    grade: str | None = None
    """The grade of the charge (e.g., summary, misdemeanor, or felony, often plus the
    degree)."""

    charge_description: str
    """The description of the charge."""

    disposition: str | None = None
    """The disposition of the charge."""

    counts: int | None = None
    """The number of counts associated with the charge."""

    sentences: list[Sentence] = Field(default_factory=list, validation_alias="sentence")
    """List of sentences associated with the charge."""


class Case(OtnMixin, CaseTypeMixin, DocketNumberMixin, CountyMixin, CaseStatusMixin):
    """Represents a case, as presented in the court summary document."""

    case_state: str | None = None
    """
    The state of the case.

    Provides more specificity than, or a rationale behind, the case status.

    """

    dcn: str | None = None
    """The district control number."""

    arrest_date: datetime.date | None = None
    """The date of the related arrest."""

    disposition_date: datetime.date | None = None
    """The date of the case's disposition."""

    trial_date: datetime.date | None = None
    """
    The date of the trial.

    Only applicable to open cases for which a trial has been scheduled.

    """

    judge: str | None = None
    """The name of the judge presiding over the case."""

    defense_attorney: str | None = None
    """The name of the defense attorney representing the defendant in the case."""

    last_action_date: datetime.date | None = None
    """
    The date of the last action taken in the case.

    Only applicable to open cases.

    """

    last_action: str | None = None
    """
    The last action taken in the case.

    Only applicable to open cases.

    """

    last_action_room: str | None = None
    """
    The room in which the last action was taken in the case.

    Only applicable to open cases.

    """

    next_action_date: datetime.date | None = None
    """
    The date of the next action scheduled in the case.

    Only applicable to open cases.

    """

    next_action: str | None = None
    """
    The next action scheduled in the case.

    Only applicable to open cases.

    """

    next_action_room: str | None = None
    """
    The room in which the next action is scheduled in the case.

    Only applicable to open cases.

    """

    bail_type: str | None = None
    """
    The type of bail set for the case.

    Only applicable to Magisterial District cases.

    """

    bail_amount: float | None = None
    """
    The amount of bail set for the case.

    Only applicable to Magisterial District cases.

    """

    bail_status: str | None = None
    """
    The status of the bail set for the case.

    Only applicable to Magisterial District cases.

    """

    charges: list[Charge] = Field(default_factory=list, validation_alias="charge")
    """List of charges associated with the case."""

    @model_validator(mode="after")
    def fill_missing_values_from_docket_number(self) -> Case:
        """
        Fills in missing values for 'court_type', 'docket_type', and 'county' fields,
        based on the 'docket_number' field.

        Returns:
            Case: The updated Case instance with missing values filled in.

        """
        if self.court_type is None:
            self.court_type = CourtType.from_docket_number(self.docket_number)

        if self.docket_type is None:
            self.docket_type = DocketType.from_docket_number(self.docket_number)

        if self.county is None:
            self.county = County.from_docket_number(self.docket_number)

        return self


class CourtSummary(ParsedDocument):
    """Represents all information presented on a defendant's court summary document."""

    defendant_name: str | None = None
    """The primary defendant's full name in reverse order (e.g., "Iverson, Allen")."""

    address: str | None = None
    """
    The defendant's last known address.

    Most often comprised of city, state, and zip code.

    """

    aliases: list[str] = Field(default_factory=list, validation_alias="alias")
    """List of aliases associated with the defendant."""

    date_of_birth: datetime.date | None = None
    """The defendant's full date of birth."""

    race: str | None = None
    """The defendant's reported race."""

    hair: str | None = None
    """The defendant's reported hair color."""

    eyes: str | None = None
    """The defendant's reported eye color."""

    sex: str | None = None
    """The defendant's reported sex."""

    cases: list[Case] = Field(default_factory=list, validation_alias="case")
    """List of cases associated with the defendant."""

    _peg_path_ctx: ClassVar[ContextVar[Path]] = ContextVar("_peg_path_ctx")

    # Preprocessing constants
    _RE_STATUS: ClassVar[str] = (
        rf"{DelimiterGlyph.ATTRIBUTES_OPEN}04.*{FontWeight.BOLD}{DelimiterGlyph.ATTRIBUTES_CLOSE}$"
    )
    """Regex pattern that matches a bold status-header line produced by pypdf."""

    _RE_DOCKET_NUMBER: ClassVar[str] = (
        rf"\-\d{{4}}\s*{DelimiterGlyph.ATTRIBUTES_OPEN}06.*{FontWeight.BOLD}{DelimiterGlyph.ATTRIBUTES_CLOSE}$"
    )
    """Regex pattern that matches the end of a docket-number line produced by pypdf."""

    _CHARGE_HEADERS: ClassVar[list[str]] = [
        # -- Common Pleas --
        "OTN:",
        "DC No:",
        "Proc Status:",
        "Arrest Dt:",
        "Disp Date:",
        "Disp Judge:",
        "Legacy No:",
        "Trial Dt:",
        "Def Atty:",
        "Last  Action Date:",
        "Last Action:",
        "Last Action Room:",
        "Next Action Date:",
        "Next Action:",
        "Next Action Room:",
        # -- Magisterial District --
        "Processing Status:",
        "Arrest Date:",
        "Disp. Event Date:",
        "Last Action Date:",
        "Bail Type:",
        "Bail Amount:",
        "Bail Status:",
    ]
    """Header strings that begin charge-level detail lines in both court types."""

    @staticmethod
    def _remove_footers(text: str) -> str:
        """
        Strips repeating page-footer content from the raw PDF text.

        Each page of a court summary PDF contains a footer block (printer information,
        page numbers, ``(Continued)`` banners, etc.) that must be removed before the
        grammar can parse the document as a single unit.

        Args:
            text (str): The raw text extracted from the court summary PDF.

        Returns:
            str: The text with all footer blocks removed.

        """
        text = re.sub(
            rf"(?<=\n)MDJS.*\nPrinted:(.*\n){{,10}}[^{DelimiterGlyph.RETURN}]*{DelimiterGlyph.RETURN}(?=.*{DelimiterGlyph.ATTRIBUTES_OPEN}04.*{FontWeight.BOLD}{DelimiterGlyph.ATTRIBUTES_CLOSE})",
            "",
            text,
        )
        text = re.sub(r"(?<=\n)MDJS.*\nPrinted:(.*\n){,5}$", "\n", text)
        text = re.sub(
            rf"Printed:(.*\n){{,10}}.*\(Continued\)({DelimiterGlyph.RETURN}|.*{FontWeight.BOLD}{DelimiterGlyph.ATTRIBUTES_CLOSE})",
            "",
            text,
        )
        text = re.sub(r"Printed:(.*\n){,3}Recent entries made in the court filing.*\n", "", text)
        return text

    @staticmethod
    def _handle_status_line(
        line: str,
        current_status: str,
        current_county: str,
        output_lines: list[str],
    ) -> tuple[str, str]:
        """
        Processes a bold status-header line, updating ``current_status`` and
        ``current_county`` in place (via ``output_lines`` mutation) and returning the
        new values.

        When the line contains embedded ``RETURN`` characters (i.e., multiple fields
        were concatenated by pypdf), the county and status are extracted from the
        appropriate positions. When there are no embedded returns, or the line is an
        Aliases header, it is appended to output unchanged.

        Args:
            line (str): The raw line matched as a status header.
            current_status (str): The currently active status string.
            current_county (str): The currently active county string.
            output_lines (list[str]): The accumulating output lines (mutated in place).

        Returns:
            tuple[str, str]: The updated ``(current_status, current_county)``.

        """
        R = DelimiterGlyph.RETURN

        if R not in line or "Aliases:" in line:
            output_lines.append(line)
            return line, current_county

        if current_status == "":
            subject_name, line = line.split(R, 1)
            attributes = re.search(CourtSummary._RE_STATUS, line).group(0)
            output_lines.append(subject_name + attributes)

        count = line.count(R)
        new_county = current_county
        if count == 1:
            new_county, line = line.split(R)
        elif count == 2:
            new_county, _, line = line.split(R)
        elif count == 3:
            _, _, new_county, line = line.split(R)

        new_status = line.rsplit(R, 1)[-1]
        return new_status, new_county

    @staticmethod
    def _handle_docket_number_line(
        line: str,
        current_status: str,
        current_case: list[str],
        current_county: str,
        output_lines: list[str],
    ) -> tuple[str, list[str]]:
        """
        Processes a docket-number line, updating ``current_county`` and ``current_case``
        and appending to ``output_lines`` where appropriate.

        If the docket number is already present in the current case (i.e., a
        page-break duplicate), the line is ignored and the existing state is
        returned unchanged.

        Args:
            line (str): The raw line matched as a docket-number line.
            current_status (str): The currently active status string.
            current_case (list[str]): Lines belonging to the current case.
            current_county (str): The currently active county string.
            output_lines (list[str]): The accumulating output lines (mutated in place).

        Returns:
            tuple[str, list[str]]: The updated ``(current_county, current_case)``.

        """
        R = DelimiterGlyph.RETURN

        if current_case and line.split(DelimiterGlyph.ATTRIBUTES_OPEN)[0] in current_case[0]:
            return current_county, current_case

        current_case = []

        if current_status.split(DelimiterGlyph.ATTRIBUTES_OPEN)[0] not in output_lines[-1]:
            output_lines.append(current_status)

        count = line.count(R)
        new_county = current_county
        if count == 1:
            new_county, _ = line.split(R)
        elif count == 2:
            _, line = line.split(R, 1)
            new_county, _ = line.split(R)
        else:
            line = R.join([new_county, line])

        output_lines.append(line)
        current_case.append(line)
        return new_county, current_case

    @staticmethod
    def _is_duplicate_case_line(line: str, current_case: list[str]) -> bool:
        """
        Returns ``True`` if ``line`` is a page-break duplicate that should be
        suppressed.

        A line is considered a duplicate when it already appears in the current
        case's accumulated lines and is either a bold-formatted field or starts
        with a known charge-header prefix.

        Args:
            line (str): The line to test.
            current_case (list[str]): Lines already accumulated for the current case.

        Returns:
            bool: ``True`` if the line should be skipped; ``False`` otherwise.

        """
        return line in current_case and (
            line.endswith(FontWeight.BOLD + DelimiterGlyph.ATTRIBUTES_CLOSE)
            or any(line.startswith(h) for h in CourtSummary._CHARGE_HEADERS)
        )

    @staticmethod
    def _preprocess(text: str) -> str:
        """
        Preprocesses the raw text extracted from the court summary PDF to remove
        extraneous content and structure it for parsing.

        Footer blocks are removed first; then the text is split into lines and
        processed through a lightweight state machine that tracks the current
        status header, county, and case context to suppress page-break duplicates.

        Args:
            text (str): The raw text extracted from the court summary PDF.

        Returns:
            str: The preprocessed text, ready for parsing.

        """
        text = CourtSummary._remove_footers(text)

        input_lines = text.split(DelimiterGlyph.END_OBJECT)
        output_lines: list[str] = []

        current_status = ""
        current_county = ""
        current_case: list[str] = []

        for line in input_lines:
            if line.startswith("Statewide") or not line.strip():
                continue
            elif re.search(CourtSummary._RE_STATUS, line):
                current_status, current_county = CourtSummary._handle_status_line(
                    line, current_status, current_county, output_lines
                )
            elif re.search(CourtSummary._RE_DOCKET_NUMBER, line):
                current_county, current_case = CourtSummary._handle_docket_number_line(
                    line, current_status, current_case, current_county, output_lines
                )
            elif current_case:
                if not CourtSummary._is_duplicate_case_line(line, current_case):
                    output_lines.append(line)
                    current_case.append(line)
            else:
                output_lines.append(line)

        return DelimiterGlyph.END_OBJECT.join(output_lines) + DelimiterGlyph.END_OBJECT

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        """
        Raises an exception if the HTTP response contains an unsuccessful status code.

        Args:
            response (httpx.Response): The HTTP response object.

        Raises:
            SealedCaseError: If the response contains a "no data found for the report" message.
            httpx.HTTPError: If the response contains an unsuccessful status code.

        """
        if "no data found for the report" in response.text.lower():
            raise SealedCaseError

        response.raise_for_status()

    @staticmethod
    def _raise_for_invalid_content(content: bytes) -> None:
        """
        Raises an InvalidResponseError if the response content is not a valid PDF file,
        is an empty PDF file, or does not appear to be a valid court document.

        Args:
            content (bytes): The response content to validate.

        Raises:
            InvalidResponseError: If the response content is not a valid PDF file,
                is an empty PDF file, or does not appear to be a valid court document.

        """
        try:
            reader = PdfReader(io.BytesIO(content))
            if not reader.pages:
                raise InvalidResponseError(message="Response content is an empty PDF file.")

            text = reader.pages[0].extract_text() or ""
            if not ("CPCMS" in text or "MDJS" in text) and ("Court Summary" in text or "DOCKET" in text):
                raise InvalidResponseError(message="Response content is not a recognized court document.")

        except PdfReadError as e:
            raise InvalidResponseError(message="Response content is not a valid PDF file.") from e

        except EmptyFileError as e:
            raise InvalidResponseError(message="Response content is an empty PDF file.") from e

    @staticmethod
    @retry_x3
    def _fetch(query_string: str) -> bytes:
        """
        Fetches a court summary PDF from the UJS portal.

        Constructs the full URL from ``Constant.BASE_URL`` and the provided query string,
        then issues a GET request using ``CourtRequestHeaders``. Respects the ``HTTP_PROXY``
        environment variable when present. Validates both the HTTP response status and the
        returned content before returning.

        Args:
            query_string (str): The URL path and query parameters identifying the court
                summary (e.g. ``/Report/CpCourtSummary?docketNumber=...&dnh=...``).

        Returns:
            bytes: The raw PDF content of the court summary.

        Raises:
            SealedCaseError: If the response body indicates no data was found (sealed case).
            httpx.HTTPStatusError: If the server returns an unsuccessful HTTP status code.
            InvalidResponseError: If the response body is not a valid or recognizable court
                summary PDF.

        """
        logger.info("Fetching case summary...")

        url = Constant.BASE_URL + query_string
        headers = CourtRequestHeaders().model_dump(exclude_none=True)

        if proxy := os.environ.get("HTTP_PROXY"):
            with httpx.Client(proxy=proxy) as client:
                response = client.get(url=url, headers=headers, timeout=30)
        else:
            response = httpx.get(url=url, headers=headers, timeout=30)

        CourtSummary._raise_for_status(response)

        pdf_bytes = response.content
        CourtSummary._raise_for_invalid_content(pdf_bytes)

        logger.info("Court summary fetched successfully.")

        return pdf_bytes

    @classmethod
    def grammar(cls) -> Grammar:
        """
        Returns a ``Grammar`` instance for the current court type.

        Reads the PEG grammar path from ``_peg_path_ctx``, which must be set by an
        entry-point method (``from_query_string`` or ``from_related_docket_number``)
        before ``from_bytes`` is called. The court-type-specific grammar is merged with
        the shared grammar common to all court summary formats.

        Returns:
            Grammar: The combined grammar for the active court type.

        Raises:
            LookupError: If ``_peg_path_ctx`` has not been set in the current context.

        """
        _peg_path = cls._peg_path_ctx.get()

        common_grammar_path = importlib.resources.files(__package__).joinpath("./grammars/shared.peg")
        grammar_path = importlib.resources.files(__package__).joinpath(str(_peg_path))

        return Grammar([grammar_path, common_grammar_path])

    @classmethod
    def from_query_string(cls, query_string: str) -> CourtSummary:
        """
        Fetches and parses a court summary from a UJS portal query string.

        The court type (Common Pleas or Magisterial District) is inferred from the
        query string path (``/Cp`` or ``/Mdj``), which determines which PEG grammar
        is used to parse the resulting PDF.

        Args:
            query_string (str): The URL path and query parameters for the court summary
                (e.g. ``/Report/CpCourtSummary?docketNumber=...&dnh=...``).

        Returns:
            CourtSummary: The parsed court summary.

        Raises:
            InvalidQueryStringError: If the query string cannot be mapped to a known
                court type.
            SealedCaseError: If the case is sealed and the document is unavailable.
            InvalidResponseError: If the fetched content is not a valid court summary PDF.

        """
        if "/Mdj" in query_string:
            _ = cls._peg_path_ctx.set(Path("./grammars/magisterial_district.peg"))
        elif "/Cp" in query_string:
            _ = cls._peg_path_ctx.set(Path("./grammars/common_pleas.peg"))
        else:
            raise InvalidQueryStringError(query_string)

        pdf_bytes = cls._fetch(query_string)
        return cls.from_bytes(pdf_bytes)

    @classmethod
    def from_related_docket_number(cls, docket_number: str) -> CourtSummary:
        """
        Fetches and parses a court summary by docket number.

        Looks up case filings for the given docket number and uses the court summary
        URL from the first result to fetch and parse the document.

        Args:
            docket_number (str): The docket number of the case (e.g. ``CP-51-CR-0001234-2020``).

        Returns:
            CourtSummary: The parsed court summary.

        Raises:
            NoFilingsFoundError: If no case filings are found for the docket number.
            NoCourtSummaryUrlError: If the case filing does not include a court summary URL.
            InvalidQueryStringError: If the court summary URL cannot be mapped to a known
                court type.
            SealedCaseError: If the case is sealed and the document is unavailable.
            InvalidResponseError: If the fetched content is not a valid court summary PDF.

        """
        case_filing = CaseFiling.from_docket_number(docket_number)
        if case_filing is None:
            raise NoFilingsFoundError(docket_number)

        query_string = case_filing.court_summary_url
        if not query_string:
            raise NoCourtSummaryUrlError(docket_number)

        return cls.from_query_string(query_string)
