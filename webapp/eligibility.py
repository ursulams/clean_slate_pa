"""
Clean Slate Act eligibility engine for Pennsylvania court records.

Implements rules under Act 36 of 2023 (Clean Slate 3.0), effective Feb 12, 2024.

IMPORTANT: This engine intentionally defaults to UNCLEAR rather than giving
false positives or false negatives. Real people's jobs and housing depend on
getting this right.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pa_record_retriever.court_summaries import Case, Charge, Sentence


# ---------------------------------------------------------------------------
# Verdict types
# ---------------------------------------------------------------------------

class Verdict(str, Enum):
    AUTO_SEAL = "AUTO_SEAL"
    PETITION_SEAL = "PETITION_SEAL"
    EXPUNGE = "EXPUNGE"
    NOT_ELIGIBLE = "NOT_ELIGIBLE"
    UNCLEAR = "UNCLEAR"
    ALREADY_SEALED = "ALREADY_SEALED"


VERDICT_PRIORITY = [
    Verdict.EXPUNGE,
    Verdict.AUTO_SEAL,
    Verdict.PETITION_SEAL,
    Verdict.UNCLEAR,
    Verdict.NOT_ELIGIBLE,
    Verdict.ALREADY_SEALED,
]


def best_verdict(verdicts: list[Verdict]) -> Verdict:
    """Return the highest-priority verdict from a list."""
    if not verdicts:
        return Verdict.UNCLEAR
    for v in VERDICT_PRIORITY:
        if v in verdicts:
            return v
    return Verdict.UNCLEAR


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class ChargeResult:
    charge_description: str
    statute: str | None
    grade: str | None
    disposition: str | None
    verdict: Verdict
    reason: str
    plain_language: str


@dataclass
class CaseResult:
    docket_number: str
    county: str | None
    case_status: str | None
    disposition_date: date | None
    arrest_date: date | None
    charges: list[ChargeResult] = field(default_factory=list)
    case_verdict: Verdict = Verdict.UNCLEAR
    case_summary: str = ""


@dataclass
class EligibilityResult:
    cases: list[CaseResult] = field(default_factory=list)
    overall_verdict: Verdict = Verdict.UNCLEAR
    has_pending: bool = False
    restitution_flag: str = "no"   # "yes", "no", "unsure"


# ---------------------------------------------------------------------------
# Helpers: grade classification
# ---------------------------------------------------------------------------

def _grade(charge: "Charge") -> str | None:
    """Return the normalized grade string, upper-cased."""
    if not charge.grade:
        return None
    return charge.grade.strip().upper()


def _is_summary(charge: "Charge") -> bool:
    g = _grade(charge)
    return g == "S" if g else False


def _is_m1(charge: "Charge") -> bool:
    g = _grade(charge)
    return g == "M1" if g else False


def _is_m2_or_m3(charge: "Charge") -> bool:
    g = _grade(charge)
    return g in ("M2", "M3") if g else False


def _is_felony(charge: "Charge") -> bool:
    g = _grade(charge)
    return g in ("F", "F1", "F2", "F3") if g else False


def _is_f3_or_ungraded_f(charge: "Charge") -> bool:
    """F or F3 — enumerated non-violent felonies (theft, forgery, fraud)."""
    g = _grade(charge)
    return g in ("F", "F3") if g else False


# ---------------------------------------------------------------------------
# Helpers: disposition classification
# ---------------------------------------------------------------------------

NON_CONVICTION_DISPOSITIONS = {
    "not guilty",
    "dismissed",
    "withdrawn",
    "nolle prossed",
    "nolle pros",
    "nol pros",
    "nol prossed",
    "acquitted",
    "not guilty by reason of insanity",
}

ARD_DISPOSITIONS = {"ard", "accelerated rehabilitative disposition"}

GUILTY_DISPOSITIONS = {"guilty", "guilty plea", "plea of guilty"}


def _disposition_lower(charge: "Charge") -> str | None:
    if not charge.disposition:
        return None
    return charge.disposition.strip().lower()


def _is_non_conviction(charge: "Charge") -> bool:
    d = _disposition_lower(charge)
    if d is None:
        return False
    return any(d == nc or d.startswith(nc) for nc in NON_CONVICTION_DISPOSITIONS)


def _is_ard(charge: "Charge") -> bool:
    d = _disposition_lower(charge)
    if d is None:
        return False
    return any(nc in d for nc in ARD_DISPOSITIONS)


def _is_convicted(charge: "Charge") -> bool:
    d = _disposition_lower(charge)
    if d is None:
        return False
    return any(d == g or d.startswith(g) for g in GUILTY_DISPOSITIONS)


def _has_disposition(charge: "Charge") -> bool:
    return bool(charge.disposition and charge.disposition.strip())


# ---------------------------------------------------------------------------
# Helpers: statute patterns
# ---------------------------------------------------------------------------

def _statute(charge: "Charge") -> str:
    return (charge.statute or "").strip()


def _is_drug_felony(charge: "Charge") -> bool:
    """35 § 780-113 drug felonies."""
    s = _statute(charge)
    return "780-113" in s or "780113" in s


def _is_terroristic_threats(charge: "Charge") -> bool:
    """§ 2706 terroristic threats."""
    s = _statute(charge)
    return "2706" in s


def _is_sex_offense(charge: "Charge") -> bool:
    """
    Heuristic only — sex offenses requiring SORNA registration.
    If uncertain, returns False and we rely on _likely_sex_offense for UNCLEAR.
    """
    s = _statute(charge).lower()
    desc = (charge.charge_description or "").lower()
    sex_patterns = [
        "3121", "3122", "3123", "3124", "3125", "3126",  # CSCA statutes
        "rape", "sexual assault", "involuntary deviate", "indecent assault",
        "indecent exposure", "sexual abuse", "corruption of minors",
        "statutory sexual assault", "child pornography", "luring",
        "trafficking", "prostitution",
    ]
    return any(p in s or p in desc for p in sex_patterns)


def _is_violent_felony(charge: "Charge") -> bool:
    """
    Heuristic for clearly violent felonies. Defaults conservatively.
    Many violent offenses require legal judgment — we flag UNCLEAR rather
    than risk a false negative.
    """
    s = _statute(charge).lower()
    desc = (charge.charge_description or "").lower()
    violent_patterns = [
        "murder", "manslaughter", "kidnapping", "robbery", "arson",
        "aggravated assault", "simple assault",  # assault is borderline, flag unclear
        "terroristic", "possessing weapon", "firearms",
        "strangulation", "human trafficking",
    ]
    return any(p in s or p in desc for p in violent_patterns)


def _is_enumerated_nonviolent_felony(charge: "Charge") -> bool:
    """
    Enumerated non-violent felonies eligible for auto-seal after 10 years:
    theft, forgery, fraud graded F or F3.
    """
    if not _is_f3_or_ungraded_f(charge):
        return False
    desc = (charge.charge_description or "").lower()
    enumerated_patterns = ["theft", "forgery", "fraud", "deceptive", "bad checks",
                           "receiving stolen", "retail theft", "access device"]
    return any(p in desc for p in enumerated_patterns)


# ---------------------------------------------------------------------------
# Helpers: sentence parsing
# ---------------------------------------------------------------------------

def _parse_months(sentence_str: str | None) -> int | None:
    """
    Parse a sentence string like "1 Year(s) 6 Month(s)" into total months.
    Returns None if unparseable.
    """
    if not sentence_str:
        return None
    s = sentence_str.strip().lower()
    years = 0
    months = 0
    days = 0

    m = re.search(r"(\d+)\s*year", s)
    if m:
        years = int(m.group(1))
    m = re.search(r"(\d+)\s*month", s)
    if m:
        months = int(m.group(1))
    m = re.search(r"(\d+)\s*day", s)
    if m:
        days = int(m.group(1))

    total = years * 12 + months + (days // 30)
    return total if (years or months or days) else None


def _max_sentence_months(charge: "Charge") -> int | None:
    """Return the maximum sentence length in months across all sentences."""
    maxval = None
    for sent in charge.sentences:
        m = _parse_months(sent.sentence_length)
        if m is not None:
            maxval = m if maxval is None else max(maxval, m)
    return maxval


def _min_sentence_months(charge: "Charge") -> int | None:
    """Return the minimum (program_period) sentence length in months."""
    minval = None
    for sent in charge.sentences:
        m = _parse_months(sent.program_period)
        if m is not None:
            minval = m if minval is None else min(minval, m)
    return minval


# ---------------------------------------------------------------------------
# Helpers: time calculations
# ---------------------------------------------------------------------------

def _years_since(d: date | None) -> float | None:
    if d is None:
        return None
    delta = date.today() - d
    return delta.days / 365.25


def _age(dob: date | None) -> float | None:
    return _years_since(dob)


# ---------------------------------------------------------------------------
# Core: pending / disqualifying checks
# ---------------------------------------------------------------------------

PENDING_STATUSES = {"active", "active/adj. delinquent", "active/adj. dependent",
                    "active/disposed"}


def _is_pending(case: "Case") -> bool:
    if case.case_status is None:
        return False
    return case.case_status.strip().lower() in PENDING_STATUSES


def _is_already_sealed(case: "Case") -> bool:
    return (case.case_status or "").strip().lower() == "sealed"


# ---------------------------------------------------------------------------
# Core: "no subsequent conviction" check
# ---------------------------------------------------------------------------

def _subsequent_conviction_date(
    ref_date: date, all_cases: list["Case"]
) -> date | None:
    """
    Return the earliest conviction date that occurs AFTER ref_date,
    across all cases. Returns None if there are no subsequent convictions.
    """
    earliest = None
    for c in all_cases:
        if c.disposition_date is None or c.disposition_date <= ref_date:
            continue
        for ch in c.charges:
            if _is_convicted(ch):
                if earliest is None or c.disposition_date < earliest:
                    earliest = c.disposition_date
    return earliest


def _subsequent_felony_or_misdemeanor_conviction(
    ref_date: date, all_cases: list["Case"]
) -> bool:
    """True if any F or M conviction appears after ref_date."""
    for c in all_cases:
        if c.disposition_date is None or c.disposition_date <= ref_date:
            continue
        for ch in c.charges:
            if _is_convicted(ch) and (_is_felony(ch) or _is_m1(ch) or _is_m2_or_m3(ch)):
                return True
    return False


def _most_recent_arrest_date(all_cases: list["Case"]) -> date | None:
    """Most recent arrest date across all cases."""
    dates = [c.arrest_date for c in all_cases if c.arrest_date]
    return max(dates) if dates else None


# ---------------------------------------------------------------------------
# Per-charge eligibility
# ---------------------------------------------------------------------------

def _evaluate_charge(
    charge: "Charge",
    case: "Case",
    all_cases: list["Case"],
    dob: date | None,
    restitution_flag: str,
) -> ChargeResult:
    """
    Evaluate a single charge and return a ChargeResult.
    Defaults to UNCLEAR when data is insufficient or ambiguous.
    """
    disp_date = case.disposition_date
    years_since_disp = _years_since(disp_date)

    # --- Already sealed ---
    if _is_already_sealed(case):
        return ChargeResult(
            charge_description=charge.charge_description,
            statute=charge.statute,
            grade=charge.grade,
            disposition=charge.disposition,
            verdict=Verdict.ALREADY_SEALED,
            reason="Case is already sealed.",
            plain_language="This case is already sealed from public view.",
        )

    # --- Pending case — disqualifying ---
    if _is_pending(case):
        return ChargeResult(
            charge_description=charge.charge_description,
            statute=charge.statute,
            grade=charge.grade,
            disposition=charge.disposition,
            verdict=Verdict.NOT_ELIGIBLE,
            reason="Case is currently active/pending.",
            plain_language="You have open charges on this case right now. You can't seal a case that's still in court.",
        )

    # --- Sex offense — always flag UNCLEAR ---
    if _is_sex_offense(charge):
        return ChargeResult(
            charge_description=charge.charge_description,
            statute=charge.statute,
            grade=charge.grade,
            disposition=charge.disposition,
            verdict=Verdict.UNCLEAR,
            reason="Possible sex offense — requires legal review.",
            plain_language="This charge may involve a sex offense. These cases need a lawyer to review — they cannot be sealed or expunged under most circumstances.",
        )

    # --- No disposition: cannot evaluate ---
    if not _has_disposition(charge):
        return ChargeResult(
            charge_description=charge.charge_description,
            statute=charge.statute,
            grade=charge.grade,
            disposition=charge.disposition,
            verdict=Verdict.UNCLEAR,
            reason="No disposition found — cannot evaluate.",
            plain_language="We couldn't find a final outcome for this charge. A lawyer can help figure out what happened.",
        )

    # ===================================================================
    # NON-CONVICTION CHARGES (dismissed, withdrawn, nolle prossed, not guilty)
    # ===================================================================
    if _is_non_conviction(charge):
        # Expungement: non-conviction charges — no waiting period
        return ChargeResult(
            charge_description=charge.charge_description,
            statute=charge.statute,
            grade=charge.grade,
            disposition=charge.disposition,
            verdict=Verdict.EXPUNGE,
            reason="Non-conviction charge (dismissed/withdrawn/not guilty) — eligible for expungement.",
            plain_language="This charge was dismissed, dropped, or you were found not guilty. It can likely be fully erased (expunged) from your record.",
        )

    # ===================================================================
    # ARD (Accelerated Rehabilitative Disposition)
    # ===================================================================
    if _is_ard(charge):
        return ChargeResult(
            charge_description=charge.charge_description,
            statute=charge.statute,
            grade=charge.grade,
            disposition=charge.disposition,
            verdict=Verdict.EXPUNGE,
            reason="Completed ARD — eligible for expungement.",
            plain_language="You completed ARD (a diversion program) on this charge. That means it can likely be fully erased (expunged) from your record.",
        )

    # ===================================================================
    # CONVICTION CHARGES — check restitution first
    # ===================================================================
    if not _is_convicted(charge):
        # Unknown disposition — can't classify
        return ChargeResult(
            charge_description=charge.charge_description,
            statute=charge.statute,
            grade=charge.grade,
            disposition=charge.disposition,
            verdict=Verdict.UNCLEAR,
            reason=f"Disposition '{charge.disposition}' not recognized — needs legal review.",
            plain_language="We couldn't recognize the outcome of this charge. A free lawyer can help you figure out if it can be sealed.",
        )

    # Restitution: if owed or unsure, flag as UNCLEAR
    if restitution_flag in ("yes", "unsure"):
        label = "still owed" if restitution_flag == "yes" else "possibly still owed"
        return ChargeResult(
            charge_description=charge.charge_description,
            statute=charge.statute,
            grade=charge.grade,
            disposition=charge.disposition,
            verdict=Verdict.UNCLEAR,
            reason=f"Restitution may be {label} — needs legal review.",
            plain_language=f"Money may still be owed to the court or a victim on this case. Unpaid restitution can block sealing. A free lawyer can check this for you before you file.",
        )

    # --- Violent felony heuristic ---
    if _is_felony(charge) and _is_violent_felony(charge):
        return ChargeResult(
            charge_description=charge.charge_description,
            statute=charge.statute,
            grade=charge.grade,
            disposition=charge.disposition,
            verdict=Verdict.UNCLEAR,
            reason="Possible violent felony — requires legal review.",
            plain_language="This charge looks like it may be a violent felony. Violent felonies usually can't be sealed, but a lawyer should confirm what category this falls under.",
        )

    # ===================================================================
    # Age 70+ expungement — applies to any conviction
    # ===================================================================
    age = _age(dob)
    if age is not None and age >= 70:
        most_recent = _most_recent_arrest_date(all_cases)
        years_since_arrest = _years_since(most_recent) if most_recent else None
        if years_since_arrest is not None and years_since_arrest >= 10:
            return ChargeResult(
                charge_description=charge.charge_description,
                statute=charge.statute,
                grade=charge.grade,
                disposition=charge.disposition,
                verdict=Verdict.EXPUNGE,
                reason="Age 70+ with 10+ arrest-free years — eligible for expungement.",
                plain_language="Because you are 70 or older and have had no arrests in the past 10 years, this record may be fully erased (expunged).",
            )

    # ===================================================================
    # SUMMARY CONVICTIONS
    # ===================================================================
    if _is_summary(charge):
        if years_since_disp is None:
            return ChargeResult(
                charge_description=charge.charge_description,
                statute=charge.statute,
                grade=charge.grade,
                disposition=charge.disposition,
                verdict=Verdict.UNCLEAR,
                reason="No disposition date — cannot calculate waiting period.",
                plain_language="We couldn't find when this case was decided. A lawyer can check if enough time has passed.",
            )
        # Check for arrest-free period (most recent arrest)
        most_recent_arrest = _most_recent_arrest_date(all_cases)
        years_since_arrest = _years_since(most_recent_arrest) if most_recent_arrest else years_since_disp

        if years_since_disp >= 5 and years_since_arrest >= 5:
            # Eligible for BOTH expungement and auto-seal — expungement is stronger
            return ChargeResult(
                charge_description=charge.charge_description,
                statute=charge.statute,
                grade=charge.grade,
                disposition=charge.disposition,
                verdict=Verdict.EXPUNGE,
                reason="Summary conviction, 5+ years, no arrest — eligible for expungement.",
                plain_language="This summary charge is 5 or more years old and you have not been arrested since. It can likely be fully erased (expunged) from your record — nothing to file.",
            )
        elif years_since_disp >= 5:
            return ChargeResult(
                charge_description=charge.charge_description,
                statute=charge.statute,
                grade=charge.grade,
                disposition=charge.disposition,
                verdict=Verdict.AUTO_SEAL,
                reason="Summary conviction, 5+ years — eligible for automatic sealing.",
                plain_language="This summary charge is 5 or more years old. It is likely being automatically sealed — no paperwork needed.",
            )
        else:
            remaining = 5 - years_since_disp
            return ChargeResult(
                charge_description=charge.charge_description,
                statute=charge.statute,
                grade=charge.grade,
                disposition=charge.disposition,
                verdict=Verdict.NOT_ELIGIBLE,
                reason=f"Summary conviction, only {years_since_disp:.1f} years since disposition (need 5).",
                plain_language=f"This summary charge needs 5 years before it can be sealed. About {remaining:.0f} more year(s) to go.",
            )

    # ===================================================================
    # MISDEMEANOR 2 / MISDEMEANOR 3
    # ===================================================================
    if _is_m2_or_m3(charge):
        if years_since_disp is None:
            return ChargeResult(
                charge_description=charge.charge_description,
                statute=charge.statute,
                grade=charge.grade,
                disposition=charge.disposition,
                verdict=Verdict.UNCLEAR,
                reason="No disposition date — cannot calculate waiting period.",
                plain_language="We couldn't find when this case was decided. A lawyer can check if enough time has passed.",
            )
        has_subsequent_fm = _subsequent_felony_or_misdemeanor_conviction(
            disp_date, all_cases
        )
        if years_since_disp >= 7 and not has_subsequent_fm:
            return ChargeResult(
                charge_description=charge.charge_description,
                statute=charge.statute,
                grade=charge.grade,
                disposition=charge.disposition,
                verdict=Verdict.AUTO_SEAL,
                reason="M2/M3, 7+ years, no subsequent F/M conviction — auto-seal eligible.",
                plain_language="This misdemeanor is 7 or more years old with no new convictions since. It is likely being automatically sealed — no paperwork needed.",
            )
        elif years_since_disp >= 7 and has_subsequent_fm:
            return ChargeResult(
                charge_description=charge.charge_description,
                statute=charge.statute,
                grade=charge.grade,
                disposition=charge.disposition,
                verdict=Verdict.NOT_ELIGIBLE,
                reason="M2/M3, 7+ years, BUT subsequent felony or misdemeanor conviction found.",
                plain_language="This misdemeanor is old enough, but a later conviction is blocking it from being sealed.",
            )
        else:
            remaining = 7 - years_since_disp
            return ChargeResult(
                charge_description=charge.charge_description,
                statute=charge.statute,
                grade=charge.grade,
                disposition=charge.disposition,
                verdict=Verdict.NOT_ELIGIBLE,
                reason=f"M2/M3, only {years_since_disp:.1f} years (need 7).",
                plain_language=f"This misdemeanor needs 7 years before it can be automatically sealed. About {remaining:.0f} more year(s) to go.",
            )

    # ===================================================================
    # MISDEMEANOR 1
    # ===================================================================
    if _is_m1(charge):
        if years_since_disp is None:
            return ChargeResult(
                charge_description=charge.charge_description,
                statute=charge.statute,
                grade=charge.grade,
                disposition=charge.disposition,
                verdict=Verdict.UNCLEAR,
                reason="No disposition date — cannot calculate waiting period.",
                plain_language="We couldn't find when this case was decided. A lawyer can check if enough time has passed.",
            )

        # Terroristic threats M1 — 10-year petition
        if _is_terroristic_threats(charge):
            if years_since_disp >= 10:
                return ChargeResult(
                    charge_description=charge.charge_description,
                    statute=charge.statute,
                    grade=charge.grade,
                    disposition=charge.disposition,
                    verdict=Verdict.PETITION_SEAL,
                    reason="Terroristic Threats §2706 M1, 10+ years — petition-based sealing eligible.",
                    plain_language="This terroristic threats charge is 10 or more years old. You may be able to seal it by filing a petition with the Court of Common Pleas in the county where you were convicted.",
                )
            else:
                remaining = 10 - years_since_disp
                return ChargeResult(
                    charge_description=charge.charge_description,
                    statute=charge.statute,
                    grade=charge.grade,
                    disposition=charge.disposition,
                    verdict=Verdict.NOT_ELIGIBLE,
                    reason=f"Terroristic Threats §2706 M1, only {years_since_disp:.1f} years (need 10).",
                    plain_language=f"This charge needs 10 years before it can be sealed. About {remaining:.0f} more year(s) to go.",
                )

        # Standard M1 — 7-year petition
        if years_since_disp >= 7:
            return ChargeResult(
                charge_description=charge.charge_description,
                statute=charge.statute,
                grade=charge.grade,
                disposition=charge.disposition,
                verdict=Verdict.PETITION_SEAL,
                reason="M1, 7+ years — petition-based sealing eligible.",
                plain_language="This misdemeanor is 7 or more years old. You may be able to seal it, but you need to file a petition with the Court of Common Pleas in the county where you were convicted.",
            )
        else:
            remaining = 7 - years_since_disp
            return ChargeResult(
                charge_description=charge.charge_description,
                statute=charge.statute,
                grade=charge.grade,
                disposition=charge.disposition,
                verdict=Verdict.NOT_ELIGIBLE,
                reason=f"M1, only {years_since_disp:.1f} years (need 7).",
                plain_language=f"This misdemeanor needs 7 years before you can petition to seal it. About {remaining:.0f} more year(s) to go.",
            )

    # ===================================================================
    # DRUG FELONIES — 35 § 780-113
    # ===================================================================
    if _is_drug_felony(charge) and _is_felony(charge):
        if years_since_disp is None:
            return ChargeResult(
                charge_description=charge.charge_description,
                statute=charge.statute,
                grade=charge.grade,
                disposition=charge.disposition,
                verdict=Verdict.UNCLEAR,
                reason="Drug felony — no disposition date, cannot calculate waiting period.",
                plain_language="We couldn't find when this case was decided. A lawyer can check if enough time has passed.",
            )

        # Check sentence length
        min_months = _min_sentence_months(charge)
        max_months = _max_sentence_months(charge)

        # If we can't determine sentence, flag UNCLEAR
        if min_months is None and max_months is None and charge.sentences:
            return ChargeResult(
                charge_description=charge.charge_description,
                statute=charge.statute,
                grade=charge.grade,
                disposition=charge.disposition,
                verdict=Verdict.UNCLEAR,
                reason="Drug felony — sentence length could not be parsed.",
                plain_language="We found a drug felony but couldn't read the sentence length. A lawyer needs to check if the sentence qualifies.",
            )

        sentence_qualifies = True
        sentence_note = ""
        if min_months is not None and min_months >= 30:
            sentence_qualifies = False
            sentence_note = f"Minimum sentence was {min_months} months (limit is 29)."
        if max_months is not None and max_months >= 60:
            sentence_qualifies = False
            sentence_note = f"Maximum sentence was {max_months} months (limit is 59)."

        has_subsequent = bool(_subsequent_conviction_date(disp_date, all_cases))

        if not sentence_qualifies:
            return ChargeResult(
                charge_description=charge.charge_description,
                statute=charge.statute,
                grade=charge.grade,
                disposition=charge.disposition,
                verdict=Verdict.NOT_ELIGIBLE,
                reason=f"Drug felony — sentence too long. {sentence_note}",
                plain_language=f"This drug felony conviction had a sentence that was too long to qualify for sealing. {sentence_note}",
            )

        if years_since_disp >= 10 and not has_subsequent:
            return ChargeResult(
                charge_description=charge.charge_description,
                statute=charge.statute,
                grade=charge.grade,
                disposition=charge.disposition,
                verdict=Verdict.AUTO_SEAL,
                reason="Drug felony §780-113, 10+ years, qualifying sentence, no subsequent conviction — auto-seal eligible.",
                plain_language="This drug felony is 10 or more years old, the sentence qualifies, and you have no new convictions. It is likely being automatically sealed — no paperwork needed.",
            )
        elif years_since_disp >= 10 and has_subsequent:
            return ChargeResult(
                charge_description=charge.charge_description,
                statute=charge.statute,
                grade=charge.grade,
                disposition=charge.disposition,
                verdict=Verdict.NOT_ELIGIBLE,
                reason="Drug felony §780-113 — 10+ years, but subsequent conviction found.",
                plain_language="This drug felony is old enough, but a later conviction is blocking it from being sealed.",
            )
        else:
            remaining = 10 - years_since_disp
            return ChargeResult(
                charge_description=charge.charge_description,
                statute=charge.statute,
                grade=charge.grade,
                disposition=charge.disposition,
                verdict=Verdict.NOT_ELIGIBLE,
                reason=f"Drug felony §780-113, only {years_since_disp:.1f} years (need 10).",
                plain_language=f"This drug felony needs 10 years before it can be automatically sealed. About {remaining:.0f} more year(s) to go.",
            )

    # ===================================================================
    # ENUMERATED NON-VIOLENT FELONIES (theft, forgery, fraud — F or F3)
    # ===================================================================
    if _is_enumerated_nonviolent_felony(charge):
        if years_since_disp is None:
            return ChargeResult(
                charge_description=charge.charge_description,
                statute=charge.statute,
                grade=charge.grade,
                disposition=charge.disposition,
                verdict=Verdict.UNCLEAR,
                reason="Enumerated felony — no disposition date.",
                plain_language="We couldn't find when this case was decided. A lawyer can check if enough time has passed.",
            )
        has_subsequent = bool(_subsequent_conviction_date(disp_date, all_cases))
        if years_since_disp >= 10 and not has_subsequent:
            return ChargeResult(
                charge_description=charge.charge_description,
                statute=charge.statute,
                grade=charge.grade,
                disposition=charge.disposition,
                verdict=Verdict.AUTO_SEAL,
                reason="Enumerated non-violent felony (theft/forgery/fraud), 10+ years, no subsequent conviction — auto-seal eligible.",
                plain_language="This felony is 10 or more years old with no new convictions since. It is likely being automatically sealed — no paperwork needed.",
            )
        elif years_since_disp >= 10 and has_subsequent:
            return ChargeResult(
                charge_description=charge.charge_description,
                statute=charge.statute,
                grade=charge.grade,
                disposition=charge.disposition,
                verdict=Verdict.NOT_ELIGIBLE,
                reason="Enumerated felony — 10+ years, but subsequent conviction found.",
                plain_language="This felony is old enough, but a later conviction is blocking it from being sealed.",
            )
        else:
            remaining = 10 - years_since_disp
            return ChargeResult(
                charge_description=charge.charge_description,
                statute=charge.statute,
                grade=charge.grade,
                disposition=charge.disposition,
                verdict=Verdict.NOT_ELIGIBLE,
                reason=f"Enumerated felony — only {years_since_disp:.1f} years (need 10).",
                plain_language=f"This felony needs 10 years before it can be automatically sealed. About {remaining:.0f} more year(s) to go.",
            )

    # ===================================================================
    # OTHER FELONIES — F1, F2, or unclassified felony not in the above
    # ===================================================================
    if _is_felony(charge):
        g = _grade(charge)
        if g in ("F1", "F2"):
            return ChargeResult(
                charge_description=charge.charge_description,
                statute=charge.statute,
                grade=charge.grade,
                disposition=charge.disposition,
                verdict=Verdict.NOT_ELIGIBLE,
                reason=f"{g} felony — not eligible for sealing under Clean Slate.",
                plain_language=f"This is a serious felony ({g}). Most serious felonies cannot be sealed. A lawyer can confirm, but this likely cannot be hidden from background checks.",
            )
        # Unclassified or ambiguous felony
        return ChargeResult(
            charge_description=charge.charge_description,
            statute=charge.statute,
            grade=charge.grade,
            disposition=charge.disposition,
            verdict=Verdict.UNCLEAR,
            reason=f"Felony grade '{charge.grade}' — eligibility unclear, needs legal review.",
            plain_language="This felony needs a lawyer to look at. The type of felony determines if it can be sealed.",
        )

    # ===================================================================
    # UNKNOWN GRADE — cannot classify
    # ===================================================================
    return ChargeResult(
        charge_description=charge.charge_description,
        statute=charge.statute,
        grade=charge.grade,
        disposition=charge.disposition,
        verdict=Verdict.UNCLEAR,
        reason=f"Grade '{charge.grade}' not recognized — needs legal review.",
        plain_language="We couldn't figure out the type of charge. A free lawyer can review this and let you know your options.",
    )


# ---------------------------------------------------------------------------
# Case-level evaluation
# ---------------------------------------------------------------------------

def _evaluate_case(
    case: "Case",
    all_cases: list["Case"],
    dob: date | None,
    restitution_flag: str,
) -> CaseResult:
    charge_results = []
    for ch in case.charges:
        r = _evaluate_charge(ch, case, all_cases, dob, restitution_flag)
        charge_results.append(r)

    # Best verdict across all charges
    verdicts = [r.verdict for r in charge_results]
    case_verdict = best_verdict(verdicts) if verdicts else Verdict.UNCLEAR

    # Human summary for the case
    if _is_already_sealed(case):
        summary = "This case is already sealed."
    elif _is_pending(case):
        summary = "This case is still open in court."
    elif case_verdict == Verdict.EXPUNGE:
        summary = "This case may qualify for full expungement."
    elif case_verdict == Verdict.AUTO_SEAL:
        summary = "Some or all charges may be automatically sealed — nothing to file."
    elif case_verdict == Verdict.PETITION_SEAL:
        summary = "You may be able to seal this case by filing a petition with the court."
    elif case_verdict == Verdict.NOT_ELIGIBLE:
        summary = "Based on what we found, this case does not appear eligible for sealing right now."
    else:
        summary = "This case needs a lawyer to review — we couldn't determine eligibility."

    return CaseResult(
        docket_number=case.docket_number,
        county=str(case.county) if case.county else None,
        case_status=str(case.case_status) if case.case_status else None,
        disposition_date=case.disposition_date,
        arrest_date=case.arrest_date,
        charges=charge_results,
        case_verdict=case_verdict,
        case_summary=summary,
    )


# ---------------------------------------------------------------------------
# Top-level entry point
# ---------------------------------------------------------------------------

def evaluate(
    cases: list["Case"],
    dob: date | None,
    restitution_flag: str = "no",
) -> EligibilityResult:
    """
    Evaluate eligibility for all cases in a court summary.

    Args:
        cases: All Case objects from a CourtSummary.
        dob: Defendant's date of birth (from CourtSummary.date_of_birth).
        restitution_flag: "yes", "no", or "unsure" — from user's answer.

    Returns:
        EligibilityResult with per-case verdicts and an overall verdict.
    """
    # Only evaluate criminal cases
    criminal_cases = [
        c for c in cases
        if str(getattr(c, "docket_type", "") or "").lower() == "criminal"
        or str(getattr(c, "docket_type", "") or "").lower() == "summary"
        or str(getattr(c, "docket_type", "") or "").lower() == "non-traffic"
        or "cr" in (c.docket_number or "").upper()
        or "su" in (c.docket_number or "").upper()[:6]
    ]

    has_pending = any(_is_pending(c) for c in criminal_cases)

    case_results = []
    for c in criminal_cases:
        cr = _evaluate_case(c, criminal_cases, dob, restitution_flag)
        case_results.append(cr)

    all_verdicts = [cr.case_verdict for cr in case_results]
    overall = best_verdict(all_verdicts) if all_verdicts else Verdict.UNCLEAR

    return EligibilityResult(
        cases=case_results,
        overall_verdict=overall,
        has_pending=has_pending,
        restitution_flag=restitution_flag,
    )
