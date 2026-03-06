import urllib.parse
from enum import StrEnum

from pydantic import AliasChoices, Field

from pa_record_retriever.pydantic import BaseModel
from pa_record_retriever.requests import RequestHeaders


class Constant:
    """Constants used in interactions with the Unified Judicial System of
    Pennsylvania."""

    BASE_URL = "https://ujsportal.pacourts.us"

    CASE_SEARCH_ENDPOINT = "/CaseSearch"
    CASE_SEARCH_COOKIE = ".AspNetCore.Antiforgery.SBFfOFqeTDE=CfDJ8Oo4u30q9HpHjge4KpOEEZ3ieV9JeAk_tLqINo7rUV7D4B_3TFv5oAP21nbxTK1YdsGtiRGi9KcX8YSPq0aM7w86eaGaNsqaemG8-izPvysXcEpn3kwvuYublLsH9f6nLPzG5FYicNx3PUTpzABJRcI; _ga=GA1.1.322318760.1738879236; _ga_PHTQNYBW14=GS1.1.1738971925.2.1.1738972248.0.0.0; _ga_62BYD7Y64T=GS1.1.1738971925.2.1.1738972248.0.0.0"
    CASE_SEARCH_TOKEN = "CfDJ8Oo4u30q9HpHjge4KpOEEZ0ao8l1tjOUmt740rZZ4p-VZi03GT79NBSkUzkGS4yiZJntn4MWJi9nzwQFW8t1n325nAHX3n2USrCyaGLdBRvh092NihhDv_oz8HVlSFxjxzmYFMN0VnRhqxV9JfSYbYY"  # noqa: S105  # CSRF antiforgery token, not a credential

    CASE_SEARCH_RESULTS_TABLE_ID = "caseSearchResultGrid"

    DOCUMENTS_ENDPOINT = "/Report"


class CourtRequestHeaders(RequestHeaders):
    """Represents the request headers used in the Unified Judicial System of
    Pennsylvania court data requests."""

    host: str = urllib.parse.urlparse(Constant.BASE_URL).netloc
    """The `Host` header, set to the base URL's netloc."""


class County(StrEnum):
    """Enumeration representing counties in Pennsylvania."""

    ADAMS = "Adams"
    ALLEGHENY = "Allegheny"
    ARMSTRONG = "Armstrong"
    BEAVER = "Beaver"
    BEDFORD = "Bedford"
    BERKS = "Berks"
    BLAIR = "Blair"
    BRADFORD = "Bradford"
    BUCKS = "Bucks"
    BUTLER = "Butler"
    CAMBRIA = "Cambria"
    CAMERON = "Cameron"
    CARBON = "Carbon"
    CENTRE = "Centre"
    CHESTER = "Chester"
    CLARION = "Clarion"
    CLEARFIELD = "Clearfield"
    CLINTON = "Clinton"
    COLUMBIA = "Columbia"
    CRAWFORD = "Crawford"
    CUMBERLAND = "Cumberland"
    DAUPHIN = "Dauphin"
    DELAWARE = "Delaware"
    ELK = "Elk"
    ERIE = "Erie"
    FAYETTE = "Fayette"
    FOREST = "Forest"
    FRANKLIN = "Franklin"
    FULTON = "Fulton"
    GREENE = "Greene"
    HUNTINGDON = "Huntingdon"
    INDIANA = "Indiana"
    JEFFERSON = "Jefferson"
    JUNIATA = "Juniata"
    LACKAWANNA = "Lackawanna"
    LANCASTER = "Lancaster"
    LAWRENCE = "Lawrence"
    LEBANON = "Lebanon"
    LEHIGH = "Lehigh"
    LUZERNE = "Luzerne"
    LYCOMING = "Lycoming"
    MCKEAN = "McKean"
    MERCER = "Mercer"
    MIFFLIN = "Mifflin"
    MONROE = "Monroe"
    MONTGOMERY = "Montgomery"
    MONTOUR = "Montour"
    NORTHAMPTON = "Northampton"
    NORTHUMBERLAND = "Northumberland"
    PERRY = "Perry"
    PHILADELPHIA = "Philadelphia"
    PIKE = "Pike"
    POTTER = "Potter"
    SCHUYLKILL = "Schuylkill"
    SNYDER = "Snyder"
    SOMERSET = "Somerset"
    SULLIVAN = "Sullivan"
    SUSQUEHANNA = "Susquehanna"
    TIOGA = "Tioga"
    UNION = "Union"
    VENANGO = "Venango"
    WARREN = "Warren"
    WASHINGTON = "Washington"
    WAYNE = "Wayne"
    WESTMORELAND = "Westmoreland"
    WYOMING = "Wyoming"
    YORK = "York"

    @property
    def county_id(self) -> str | None:
        """Two-digit county ID used in Common Pleas and Municipal Court docket numbers
        (positions 3-4)."""
        ids = {
            County.ADAMS: "01",
            County.ALLEGHENY: "02",
            County.ARMSTRONG: "03",
            County.BEAVER: "04",
            County.BEDFORD: "05",
            County.BERKS: "06",
            County.BLAIR: "07",
            County.BRADFORD: "08",
            County.BUCKS: "09",
            County.BUTLER: "10",
            County.CAMBRIA: "11",
            County.CAMERON: "12",
            County.CARBON: "13",
            County.CENTRE: "14",
            County.CHESTER: "15",
            County.CLARION: "16",
            County.CLEARFIELD: "17",
            County.CLINTON: "18",
            County.COLUMBIA: "19",
            County.CRAWFORD: "20",
            County.CUMBERLAND: "21",
            County.DAUPHIN: "22",
            County.DELAWARE: "23",
            County.ELK: "24",
            County.ERIE: "25",
            County.FAYETTE: "26",
            County.FOREST: "27",
            County.FRANKLIN: "28",
            County.FULTON: "29",
            County.GREENE: "30",
            County.HUNTINGDON: "31",
            County.INDIANA: "32",
            County.JEFFERSON: "33",
            County.JUNIATA: "34",
            County.LACKAWANNA: "35",
            County.LANCASTER: "36",
            County.LAWRENCE: "37",
            County.LEBANON: "38",
            County.LEHIGH: "39",
            County.LUZERNE: "40",
            County.LYCOMING: "41",
            County.MCKEAN: "42",
            County.MERCER: "43",
            County.MIFFLIN: "44",
            County.MONROE: "45",
            County.MONTGOMERY: "46",
            County.MONTOUR: "47",
            County.NORTHAMPTON: "48",
            County.NORTHUMBERLAND: "49",
            County.PERRY: "50",
            County.PHILADELPHIA: "51",
            County.PIKE: "52",
            County.POTTER: "53",
            County.SCHUYLKILL: "54",
            County.SNYDER: "55",
            County.SOMERSET: "56",
            County.SULLIVAN: "57",
            County.SUSQUEHANNA: "58",
            County.TIOGA: "59",
            County.UNION: "60",
            County.VENANGO: "61",
            County.WARREN: "62",
            County.WASHINGTON: "63",
            County.WAYNE: "64",
            County.WESTMORELAND: "65",
            County.WYOMING: "66",
            County.YORK: "67",
        }
        return ids.get(self)

    @property
    def judicial_district(self) -> str | None:
        """Two-digit judicial district ID used in Magisterial District docket numbers
        (positions 3-4)."""
        districts = {
            County.ADAMS: "51",
            County.ALLEGHENY: "05",
            County.ARMSTRONG: "33",
            County.BEAVER: "36",
            County.BEDFORD: "57",
            County.BERKS: "23",
            County.BLAIR: "24",
            County.BRADFORD: "42",
            County.BUCKS: "07",
            County.BUTLER: "50",
            County.CAMBRIA: "47",
            County.CAMERON: "59",
            County.CARBON: "56",
            County.CENTRE: "49",
            County.CHESTER: "15",
            County.CLARION: "18",
            County.CLEARFIELD: "46",
            County.CLINTON: "25",
            County.COLUMBIA: "26",
            County.CRAWFORD: "30",
            County.CUMBERLAND: "09",
            County.DAUPHIN: "12",
            County.DELAWARE: "32",
            County.ELK: "59",
            County.ERIE: "06",
            County.FAYETTE: "14",
            County.FOREST: "37",
            County.FRANKLIN: "39",
            County.FULTON: "39",
            County.GREENE: "13",
            County.HUNTINGDON: "20",
            County.INDIANA: "40",
            County.JEFFERSON: "54",
            County.JUNIATA: "41",
            County.LACKAWANNA: "45",
            County.LANCASTER: "02",
            County.LAWRENCE: "53",
            County.LEBANON: "52",
            County.LEHIGH: "31",
            County.LUZERNE: "11",
            County.LYCOMING: "29",
            County.MCKEAN: "48",
            County.MERCER: "35",
            County.MIFFLIN: "58",
            County.MONROE: "43",
            County.MONTGOMERY: "38",
            County.MONTOUR: "26",
            County.NORTHAMPTON: "03",
            County.NORTHUMBERLAND: "08",
            County.PERRY: "41",
            County.PHILADELPHIA: "01",
            County.PIKE: "50",
            County.POTTER: "55",
            County.SCHUYLKILL: "21",
            County.SNYDER: "17",
            County.SOMERSET: "16",
            County.SULLIVAN: "44",
            County.SUSQUEHANNA: "34",
            County.TIOGA: "04",
            County.UNION: "17",
            County.VENANGO: "28",
            County.WARREN: "37",
            County.WASHINGTON: "27",
            County.WAYNE: "22",
            County.WESTMORELAND: "10",
            County.WYOMING: "44",
            County.YORK: "19",
        }
        return districts.get(self)

    @classmethod
    def from_docket_number(cls, docket_number: str) -> str | None:
        """
        Returns the ``County`` corresponding to the given docket number.

        For Magisterial District dockets (``MJ-``), the county is matched by
        ``judicial_district`` (positions 3-4). For Common Pleas and Municipal Court
        dockets (``CP-`` / ``MC-``), it is matched by ``county_id`` (positions 3-4).

        Note: Some counties share a judicial district. In those cases the first
        matching county is returned.

        Args:
            docket_number (str): The docket number to look up.

        Returns:
            County | None: The matching ``County`` if found, otherwise ``None``.

        """
        if docket_number.startswith(f"{CourtType.MAGISTERIAL_DISTRICT.docket_prefix}-"):
            for county in cls:
                if docket_number[3:5] == county.judicial_district:
                    return county.value

        elif docket_number.startswith(f"{CourtType.COMMON_PLEAS.docket_prefix}-") or docket_number.startswith(
            f"{CourtType.MUNICIPAL_COURT.docket_prefix}-"
        ):
            for county in cls:
                if docket_number[3:5] == county.county_id:
                    return county.value


class CourtType(StrEnum):
    """Enumeration representing different types of courts in Pennsylvania."""

    MAGISTERIAL_DISTRICT = "Magisterial District"
    MUNICIPAL_COURT = "Municipal Court"
    COMMON_PLEAS = "Common Pleas"

    @property
    def docket_prefix(self) -> str | None:
        """
        Returns the docket prefix associated with the court type.

        Returns:
            str: The docket prefix for the court type.

        """
        prefixes = {
            CourtType.MAGISTERIAL_DISTRICT: "MJ",
            CourtType.MUNICIPAL_COURT: "MC",
            CourtType.COMMON_PLEAS: "CP",
        }

        return prefixes.get(self)

    @classmethod
    def from_docket_number(cls, docket_number: str) -> str | None:
        """
        Returns the ``CourtType`` corresponding to the given docket number.

        Matches by comparing the docket number prefix (e.g. ``CP-``, ``MJ-``, ``MC-``)
        against each court type's ``docket_prefix``.

        Args:
            docket_number (str): The docket number to look up.

        Returns:
            CourtType | None: The matching ``CourtType`` if found, otherwise ``None``.

        """
        for court_type in cls:
            if docket_number.startswith(f"{court_type.docket_prefix}-"):
                return court_type.value


class CaseStatus(StrEnum):
    """Enumeration representing different case statuses in Pennsylvania."""

    ACTIVE = "Active"
    """Represents an active case status."""

    ACTIVE_DELINQUENT = "Active/Adj. Delinquent"
    """Represents an active case status with adjudicated delinquency."""

    ACTIVE_DEPENDENT = "Active/Adj. Dependent"
    """Represents an active case status with adjudicated dependency."""

    ACTIVE_DISPOSED = "Active/Disposed"
    """Represents an active case status that has been disposed."""

    ADJUDICATED = "Adjudicated"
    """Represents a case status that has been adjudicated."""

    ADJUDICATED_CLOSED = "Adjudicated/Closed"
    """Represents a case status that has been adjudicated and closed."""

    ARCHIVED = "Archived"
    """Represents an archived case status."""

    CLOSED = "Closed"
    """Represents a closed case status."""

    INACTIVE = "Inactive"
    """Represents an inactive case status."""

    PHYSICAL_CASE_FILE_DESTROYED = "Physical Case File Destroyed"
    """Represents a case status where the physical case file has been destroyed."""

    SEALED = "Sealed"
    """
    Represents a sealed case status.

    Cases are presumed sealed if the related documents are no longer accessible (i.e.,
    return a 401 Unauthorized error when accessed).

    """


class DocketType(StrEnum):
    """Enumeration representing different types of dockets in Pennsylvania."""

    CIVIL = "Civil"
    CRIMINAL = "Criminal"
    LANDLORD_TENANT = "Landlord/Tenant"
    MISCELLANEOUS = "Miscellaneous"
    NON_TRAFFIC = "Non-Traffic"
    SUMMARY = "Summary"
    SUMMARY_APPEAL = "Summary Appeal"
    TRAFFIC = "Traffic"

    @property
    def docket_prefix(self) -> str | None:
        """
        Returns the docket prefix associated with the docket type.

        Returns:
            str: The docket prefix for the docket type.

        """
        prefixes = {
            DocketType.CIVIL: "CV",
            DocketType.CRIMINAL: "CR",
            DocketType.LANDLORD_TENANT: "LT",
            DocketType.MISCELLANEOUS: "MD",
            DocketType.NON_TRAFFIC: "NT",
            DocketType.SUMMARY: "SU",
            DocketType.SUMMARY_APPEAL: "SA",
            DocketType.TRAFFIC: "TR",
        }

        return prefixes.get(self)

    @classmethod
    def from_docket_number(cls, docket_number: str) -> str | None:
        """
        Returns the ``DocketType`` corresponding to the given docket number.

        Matches by checking whether the docket number contains the pattern
        ``-<prefix>-`` (e.g. ``-CR-``, ``-CV-``) for each docket type's
        ``docket_prefix``.

        Args:
            docket_number (str): The docket number to look up.

        Returns:
            DocketType | None: The matching ``DocketType`` if found, otherwise ``None``.

        """
        for docket_type in cls:
            if f"-{docket_type.docket_prefix}-" in docket_number:
                return docket_type.value


class SearchBy(StrEnum):
    """Enumeration representing different types of case search parameters in the Unified
    Judicial System of Pennsylvania."""

    APPELLATE_COURT_NAME = "AppellateCourtName"
    ATTORNEY = "Attorney"
    CALENDAR_EVENT = "CalendarEvent"
    CITATION_NUMBER = "CitationNumber"
    COMPLAINT_NUMBER = "ComplaintNumber"
    DATE_FILED = "DateFiled"
    DOCKET_NUMBER = "DocketNumber"
    INCIDENT_NUMBER = "IncidentNumber"
    ORGANIZATION = "Organization"
    OTN = "OTN"
    PARCEL = "Parcel"
    PARTICIPANT_NAME = "ParticipantName"
    SID = "SID"


class CountyMixin(BaseModel):
    """Mixin class that adds a `county` field to models, representing the Pennsylvania
    county in which a case is filed."""

    county: County | None = Field(default=None, validation_alias=AliasChoices("CountyName", "county"))
    """The county in which the case is filed."""


class DocketNumberMixin(BaseModel):
    """Mixin class that adds a `docket_number` field to models, representing the unique
    identifier for a case in the Unified Judicial System of Pennsylvania."""

    docket_number: str = Field(validation_alias=AliasChoices("DocketNumber", "docket_number"))
    """The docket number of the case, also its unique identifier."""


class CaseStatusMixin(BaseModel):
    """Mixin class that adds a `case_status` field to models, representing the status of
    a case."""

    case_status: CaseStatus | None = Field(default=None, validation_alias=AliasChoices("CaseStatus", "case_status"))
    """The status of the case."""


class OtnMixin(BaseModel):
    """Mixin class that adds an `otn` field, representing the offense tracking
    number."""

    otn: str | None = Field(default=None, validation_alias=AliasChoices("OTN", "otn"))
    """The offense tracking number."""


class CourtTypeMixin(BaseModel):
    """Mixin class that adds a `court_type` field to models, representing the type of
    court in which a case is filed."""

    court_type: CourtType | None = Field(default=None, validation_alias="CourtSystem")
    """The type of court in which the case is filed."""


class CaseTypeMixin(CourtTypeMixin):
    """Mixin class that adds `court_type` and `docket_type` fields to models,
    representing the type of court in which a case is filed and the type of case,
    respectively."""

    docket_type: DocketType | None = None
    """The type of case."""
