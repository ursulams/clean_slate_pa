"""
Clean Slate PA — FastAPI backend.

Serves the mobile-first web app and provides the /api/check endpoint that
looks up Pennsylvania court records and returns eligibility results.
"""

from __future__ import annotations

import datetime
import sys
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

# Add the repo src to the path so we can import pa_record_retriever when
# running locally without a full install (e.g. `uvicorn webapp.main:app`
# from the repo root). On Railway the package is installed via requirements.txt
# and this is a no-op.
_src = Path(__file__).parent.parent / "src"
if _src.exists():
    sys.path.insert(0, str(_src))

# Also ensure the webapp directory is on the path so `eligibility` is importable
# regardless of where uvicorn is invoked from.
_webapp = Path(__file__).parent
if str(_webapp) not in sys.path:
    sys.path.insert(0, str(_webapp))

from pa_record_retriever import CaseFiling, CourtSummary
from pa_record_retriever.court_summaries import (
    NoCourtSummaryUrlError,
    NoFilingsFoundError,
    SealedCaseError,
)
from pa_record_retriever.requests import InvalidResponseError

from eligibility import Verdict, evaluate

app = FastAPI(title="Clean Slate PA")

BASE_DIR = Path(__file__).parent
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class SearchRequest(BaseModel):
    first_name: str
    last_name: str
    date_of_birth: str  # YYYY-MM-DD


class VerifyRequest(BaseModel):
    """Second step: user confirms which cases belong to them."""
    first_name: str
    last_name: str
    date_of_birth: str
    court_summary_url: str
    restitution: str  # "yes" | "no" | "unsure"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VERDICT_META = {
    Verdict.EXPUNGE: {
        "label": "May qualify for full expungement",
        "color": "purple",
        "icon": "★",
        "headline": "Your record may be fully erasable",
        "detail": "Expungement means the record is completely destroyed — even law enforcement cannot see it.",
    },
    Verdict.AUTO_SEAL: {
        "label": "Likely automatically sealing",
        "color": "green",
        "icon": "✓",
        "headline": "Good news — this may be sealing on its own",
        "detail": "Automatic sealing means the court does it without you filing anything.",
    },
    Verdict.PETITION_SEAL: {
        "label": "May qualify — filing required",
        "color": "blue",
        "icon": "📋",
        "headline": "You may be able to seal this — but you need to file paperwork",
        "detail": "Petition sealing requires filing a form with the Court of Common Pleas in the county where you were convicted.",
    },
    Verdict.UNCLEAR: {
        "label": "Needs legal review",
        "color": "yellow",
        "icon": "?",
        "headline": "A lawyer should look at this",
        "detail": "We couldn't determine eligibility from the court data alone. A free lawyer can review this with you.",
    },
    Verdict.NOT_ELIGIBLE: {
        "label": "Not eligible right now",
        "color": "gray",
        "icon": "✗",
        "headline": "This does not appear eligible for sealing right now",
        "detail": "This may change in the future, or a lawyer may see something we missed.",
    },
    Verdict.ALREADY_SEALED: {
        "label": "Already sealed",
        "color": "teal",
        "icon": "🔒",
        "headline": "This case is already sealed",
        "detail": "Sealed records are hidden from public background checks.",
    },
}


def _serialize_case_result(cr: Any) -> dict:
    charges = []
    for ch in cr.charges:
        meta = VERDICT_META.get(ch.verdict, VERDICT_META[Verdict.UNCLEAR])
        charges.append({
            "charge_description": ch.charge_description,
            "statute": ch.statute,
            "grade": ch.grade,
            "disposition": ch.disposition,
            "verdict": ch.verdict.value,
            "plain_language": ch.plain_language,
            "meta": meta,
        })

    meta = VERDICT_META.get(cr.case_verdict, VERDICT_META[Verdict.UNCLEAR])
    return {
        "docket_number": cr.docket_number,
        "county": cr.county,
        "case_status": cr.case_status,
        "disposition_date": cr.disposition_date.isoformat() if cr.disposition_date else None,
        "case_verdict": cr.case_verdict.value,
        "case_summary": cr.case_summary,
        "meta": meta,
        "charges": charges,
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/search")
async def search(req: SearchRequest):
    """
    Step 1: Search by name + DOB.
    Returns a list of candidate cases for the user to verify.
    Each candidate shows only: initials, county, year of birth (never full name/DOB).
    """
    try:
        dob = datetime.date.fromisoformat(req.date_of_birth)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")

    try:
        filings = CaseFiling.from_defendant(
            first_name=req.first_name.strip(),
            last_name=req.last_name.strip(),
            date_of_birth=dob,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Could not reach Pennsylvania court records: {e}")

    if not filings:
        return JSONResponse({"found": False, "candidates": []})

    # Filter to criminal/summary cases only
    criminal_filings = [
        f for f in filings
        if f.docket_type and str(f.docket_type).lower() in ("criminal", "summary", "non-traffic")
        or (f.docket_number and ("-CR-" in f.docket_number.upper() or "-SU-" in f.docket_number.upper()))
    ]

    if not criminal_filings:
        return JSONResponse({"found": False, "candidates": []})

    # Group by defendant identity (name + DOB) — one card per distinct person.
    # court_summary_url carries a per-request dnh token so it differs across
    # filings for the same person and cannot be used as the grouping key.
    grouped: dict[str, dict] = {}
    for f in criminal_filings:
        name_raw = (f.defendant_name or "").strip()
        dob_raw = str(f.defendant_date_of_birth) if f.defendant_date_of_birth else ""
        key = f"{name_raw}|{dob_raw}"

        if key not in grouped:
            name_parts = name_raw.split(",")
            last_init = name_parts[0].strip()[0].upper() if name_parts and name_parts[0].strip() else "?"
            first_init = name_parts[1].strip()[0].upper() if len(name_parts) > 1 and name_parts[1].strip() else "?"
            initials = f"{last_init}.{first_init}."
            county = str(f.county) if f.county else "Unknown county"
            birth_year = f.defendant_date_of_birth.year if f.defendant_date_of_birth else "Unknown year"

            grouped[key] = {
                "court_summary_url": f.court_summary_url,
                "initials": initials,
                "county": county,
                "birth_year": birth_year,
                "case_count": 1,
                "filing_years": [f.filing_date.year] if f.filing_date else [],
            }
        else:
            grouped[key]["case_count"] += 1
            if f.filing_date:
                grouped[key]["filing_years"].append(f.filing_date.year)
            # Prefer a non-None court_summary_url
            if grouped[key]["court_summary_url"] is None and f.court_summary_url:
                grouped[key]["court_summary_url"] = f.court_summary_url

    # Compute filing year range and drop the raw list before sending to client
    for entry in grouped.values():
        years = entry.pop("filing_years")
        entry["filing_year_min"] = min(years) if years else None
        entry["filing_year_max"] = max(years) if years else None

    candidates = list(grouped.values())

    return JSONResponse({
        "found": True,
        "candidates": candidates,
        "multiple": len(candidates) > 1,
    })


@app.post("/api/check")
async def check(req: VerifyRequest):
    """
    Step 2: Fetch the full court summary and run eligibility analysis.
    Called after user confirms their cases and answers the restitution question.
    """
    if not req.court_summary_url:
        raise HTTPException(status_code=400, detail="court_summary_url is required.")

    if req.restitution not in ("yes", "no", "unsure"):
        raise HTTPException(status_code=400, detail="restitution must be 'yes', 'no', or 'unsure'.")

    try:
        summary = CourtSummary.from_query_string(req.court_summary_url)
    except SealedCaseError:
        return JSONResponse({
            "status": "sealed",
            "message": "It looks like your record may already be sealed. That's a good thing! If you're not sure, contact a free lawyer to confirm.",
        })
    except (NoFilingsFoundError, NoCourtSummaryUrlError):
        raise HTTPException(status_code=404, detail="No court records found.")
    except InvalidResponseError as e:
        raise HTTPException(status_code=502, detail=f"Court records returned an unexpected response: {e}")
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"Could not reach Pennsylvania court records: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")

    result = evaluate(
        cases=summary.cases,
        dob=summary.date_of_birth,
        restitution_flag=req.restitution,
    )

    serialized_cases = [_serialize_case_result(cr) for cr in result.cases]

    overall_meta = VERDICT_META.get(result.overall_verdict, VERDICT_META[Verdict.UNCLEAR])

    return JSONResponse({
        "status": "ok",
        "overall_verdict": result.overall_verdict.value,
        "overall_meta": overall_meta,
        "has_pending": result.has_pending,
        "cases": serialized_cases,
        "case_count": len(serialized_cases),
    })


@app.get("/health")
async def health():
    return {"status": "ok"}
