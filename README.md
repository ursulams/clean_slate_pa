# pa-ujs-document-parser

A Python library for fetching and parsing public court records from the [Pennsylvania Unified Judicial System (UJS) portal](https://ujsportal.pacourts.us). It provides structured, typed data for case filings and court summary documents across Common Pleas, Municipal Court, and Magisterial District courts.

## Installation

```bash
pip install pa-ujs-document-parser
```

## Overview

The library exposes two primary classes:

- **`CaseFiling`** — retrieves case-level filing records from the UJS case search
- **`CourtSummary`** — fetches and parses a defendant's full court summary PDF

Both are Pydantic models. All fields are validated and typed on the way in, and can be serialized to a dict or JSON via standard Pydantic methods (`.model_dump()`, `.model_dump_json()`).

## Usage

### Fetching case filings

Search by docket number to retrieve all filings associated with a case:

```python
from pa_ujs_document_parser import CaseFiling

filings = CaseFiling.from_related_docket_number("CP-51-CR-0001234-2020")
```

Or search by defendant name (optionally narrowed by date of birth):

```python
from datetime import date
from pa_ujs_document_parser import CaseFiling

filings = CaseFiling.from_defendant(
    first_name="Allen",
    last_name="Iverson",
    date_of_birth=date(1975, 6, 7),
)
```

Each result is a `CaseFiling` with the following key fields:

| Field                     | Type                 | Description                                            |
| ------------------------- | -------------------- | ------------------------------------------------------ |
| `docket_number`           | `str`                | Unique case identifier                                 |
| `court_type`              | `CourtType \| None`  | Common Pleas, Municipal Court, or Magisterial District |
| `docket_type`             | `DocketType \| None` | Criminal, Civil, Traffic, etc.                         |
| `county`                  | `County \| None`     | Pennsylvania county                                    |
| `case_status`             | `CaseStatus \| None` | Active, Closed, Archived, etc.                         |
| `filing_date`             | `date`               | Date the case was filed                                |
| `defendant_name`          | `str \| None`        | Full name in reverse order (e.g. `"Iverson, Allen"`)   |
| `defendant_date_of_birth` | `date \| None`       | Defendant's date of birth                              |
| `otn`                     | `str \| None`        | Offense tracking number                                |
| `court_summary_url`       | `str \| None`        | Query string for the court summary PDF (see below)     |
| `docket_sheet_url`        | `str \| None`        | Query string for the docket sheet PDF                  |

### Fetching a court summary

A court summary aggregates all criminal history for a defendant across all associated cases. Fetch one directly by docket number:

```python
from pa_ujs_document_parser import CourtSummary

summary = CourtSummary.from_related_docket_number("CP-51-CR-0001234-2020")
```

Or fetch from a court summary URL obtained from a `CaseFiling`:

```python
filings = CaseFiling.from_related_docket_number("CP-51-CR-0001234-2020")
summary = CourtSummary.from_query_string(filings[0].court_summary_url)
```

The returned `CourtSummary` has the following top-level fields:

| Field            | Type           | Description                             |
| ---------------- | -------------- | --------------------------------------- |
| `defendant_name` | `str \| None`  | Full name in reverse order              |
| `date_of_birth`  | `date \| None` | Defendant's date of birth               |
| `address`        | `str \| None`  | Last known address                      |
| `aliases`        | `list[str]`    | Known aliases                           |
| `race`           | `str \| None`  | Reported race                           |
| `sex`            | `str \| None`  | Reported sex                            |
| `hair`           | `str \| None`  | Reported hair color                     |
| `eyes`           | `str \| None`  | Reported eye color                      |
| `cases`          | `list[Case]`   | All cases associated with the defendant |

#### Cases

Each `Case` within a `CourtSummary` contains:

| Field              | Type                 | Description                       |
| ------------------ | -------------------- | --------------------------------- |
| `docket_number`    | `str`                | Unique case identifier            |
| `court_type`       | `CourtType \| None`  |                                   |
| `docket_type`      | `DocketType \| None` |                                   |
| `county`           | `County \| None`     |                                   |
| `case_status`      | `CaseStatus \| None` |                                   |
| `otn`              | `str \| None`        | Offense tracking number           |
| `dcn`              | `str \| None`        | District control number           |
| `arrest_date`      | `date \| None`       |                                   |
| `disposition_date` | `date \| None`       |                                   |
| `trial_date`       | `date \| None`       | Open cases with a scheduled trial |
| `judge`            | `str \| None`        | Presiding judge                   |
| `defense_attorney` | `str \| None`        |                                   |
| `last_action_date` | `date \| None`       | Open cases only                   |
| `last_action`      | `str \| None`        | Open cases only                   |
| `next_action_date` | `date \| None`       | Open cases only                   |
| `next_action`      | `str \| None`        | Open cases only                   |
| `bail_type`        | `str \| None`        | Magisterial District cases only   |
| `bail_amount`      | `float \| None`      | Magisterial District cases only   |
| `bail_status`      | `str \| None`        | Magisterial District cases only   |
| `charges`          | `list[Charge]`       |                                   |

#### Charges and sentences

Each `Charge` contains:

| Field                | Type             | Description                        |
| -------------------- | ---------------- | ---------------------------------- |
| `sequence_number`    | `int \| None`    | Charge sequence within the case    |
| `statute`            | `str \| None`    | Applicable statute                 |
| `grade`              | `str \| None`    | e.g. `"F1"`, `"M2"`, `"S"`         |
| `charge_description` | `str`            | Plain-text charge description      |
| `disposition`        | `str \| None`    | e.g. `"Guilty"`, `"Nolle Prossed"` |
| `counts`             | `int \| None`    | Number of counts                   |
| `sentences`          | `list[Sentence]` |                                    |

Each `Sentence` contains:

| Field             | Type          | Description                              |
| ----------------- | ------------- | ---------------------------------------- |
| `sentence_date`   | `date`        |                                          |
| `sentence_type`   | `str`         | e.g. `"Probation"`, `"Confinement"`      |
| `program_period`  | `str \| None` | Minimum length for confinement sentences |
| `sentence_length` | `str \| None` |                                          |

### Serialization

All returned objects are Pydantic models and support standard serialization:

```python
summary = CourtSummary.from_related_docket_number("CP-51-CR-0001234-2020")

# Dict
data = summary.model_dump()

# JSON string
json_str = summary.model_dump_json()
```

## Error handling

The following exceptions may be raised by the public API:

| Exception                 | Raised when                                                                      |
| ------------------------- | -------------------------------------------------------------------------------- |
| `SealedCaseError`         | The case is sealed or expunged and documents are unavailable                     |
| `NoFilingsFoundError`     | No case filings are found for the given docket number                            |
| `NoCourtSummaryUrlError`  | The case filing does not include a court summary URL                             |
| `InvalidQueryStringError` | The query string cannot be mapped to a known court type                          |
| `EmptyFieldError`         | A required string argument (`first_name`, `last_name`, `docket_number`) is empty |
| `InvalidResponseError`    | The UJS portal returned an unexpected or malformed response                      |
| `httpx.HTTPStatusError`   | The UJS portal returned an unsuccessful HTTP status code                         |

```python
from pa_ujs_document_parser import CourtSummary
from pa_ujs_document_parser.court_summaries import SealedCaseError, NoFilingsFoundError

try:
    summary = CourtSummary.from_related_docket_number("CP-51-CR-0001234-2020")
except SealedCaseError:
    print("Case is sealed.")
except NoFilingsFoundError:
    print("No filings found for that docket number.")
```

## Proxy support

Both `CaseFiling` and `CourtSummary` respect the `HTTP_PROXY` environment variable when making requests:

```bash
HTTP_PROXY=http://your.proxy:8080 python your_script.py
```
