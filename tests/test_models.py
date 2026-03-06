from pa_record_retriever.models import (
    CaseStatus,
    CaseStatusMixin,
    CaseTypeMixin,
    Constant,
    County,
    CountyMixin,
    CourtRequestHeaders,
    CourtType,
    CourtTypeMixin,
    DocketNumberMixin,
    DocketType,
    OtnMixin,
    SearchBy,
)


class TestConstant:
    """Tests for the ``Constant`` class."""

    def test_base_url(self) -> None:
        """``BASE_URL`` points to the UJS portal."""
        assert Constant.BASE_URL == "https://ujsportal.pacourts.us"

    def test_case_search_endpoint(self) -> None:
        """``CASE_SEARCH_ENDPOINT`` is the correct path."""
        assert Constant.CASE_SEARCH_ENDPOINT == "/CaseSearch"

    def test_case_search_results_table_id(self) -> None:
        """``CASE_SEARCH_RESULTS_TABLE_ID`` matches the expected HTML element id."""
        assert Constant.CASE_SEARCH_RESULTS_TABLE_ID == "caseSearchResultGrid"

    def test_documents_endpoint(self) -> None:
        """``DOCUMENTS_ENDPOINT`` is the correct path."""
        assert Constant.DOCUMENTS_ENDPOINT == "/Report"


class TestCourtRequestHeaders:
    """Tests for the ``CourtRequestHeaders`` model."""

    def test_host_is_ujsportal(self) -> None:
        """The ``host`` field is the netloc of the base URL."""
        headers = CourtRequestHeaders()
        assert headers.host == "ujsportal.pacourts.us"

    def test_inherits_user_agent(self) -> None:
        """``user_agent`` is inherited from ``RequestHeaders``."""
        headers = CourtRequestHeaders()
        assert headers.user_agent.startswith("Mozilla")


class TestCounty:
    """Tests for the ``County`` StrEnum."""

    class TestCountyId:
        """Tests for the ``County.county_id`` property."""

        def test_philadelphia_county_id(self) -> None:
            """Philadelphia has county ID ``"51"``."""
            assert County.PHILADELPHIA.county_id == "51"

        def test_adams_county_id(self) -> None:
            """Adams has county ID ``"01"``."""
            assert County.ADAMS.county_id == "01"

        def test_york_county_id(self) -> None:
            """York (last alphabetically) has county ID ``"67"``."""
            assert County.YORK.county_id == "67"

        def test_all_counties_have_two_digit_ids(self) -> None:
            """Every county returns a two-digit string county ID."""
            for county in County:
                assert len(county.county_id) == 2

    class TestJudicialDistrict:
        """Tests for the ``County.judicial_district`` property."""

        def test_philadelphia_judicial_district(self) -> None:
            """Philadelphia is judicial district ``"01"``."""
            assert County.PHILADELPHIA.judicial_district == "01"

        def test_lancaster_judicial_district(self) -> None:
            """Lancaster is judicial district ``"02"``."""
            assert County.LANCASTER.judicial_district == "02"

        def test_all_counties_have_two_digit_districts(self) -> None:
            """Every county returns a two-digit string judicial district."""
            for county in County:
                assert len(county.judicial_district) == 2

    class TestFromDocketNumber:
        """Tests for ``County.from_docket_number``."""

        def test_cp_docket_returns_county(self) -> None:
            """A Common Pleas docket (``CP-51-...``) maps to Philadelphia."""
            result = County.from_docket_number("CP-51-CR-0001234-2020")
            assert result == County.PHILADELPHIA

        def test_mc_docket_returns_county(self) -> None:
            """A Municipal Court docket (``MC-51-...``) maps to Philadelphia."""
            result = County.from_docket_number("MC-51-CR-0001234-2020")
            assert result == County.PHILADELPHIA

        def test_mj_docket_returns_county(self) -> None:
            """An MJ docket is matched by judicial district."""
            result = County.from_docket_number("MJ-01-CR-0001234-2020")
            assert result == County.PHILADELPHIA

        def test_unknown_prefix_returns_none(self) -> None:
            """An unrecognized prefix returns ``None``."""
            result = County.from_docket_number("XX-51-CR-0001234-2020")
            assert result is None

        def test_cp_adams_county(self) -> None:
            """CP-01- maps to Adams County."""
            result = County.from_docket_number("CP-01-CR-0001234-2020")
            assert result == County.ADAMS

        def test_mj_lancaster_county(self) -> None:
            """MJ-02- maps to Lancaster (judicial district 02)."""
            result = County.from_docket_number("MJ-02-CR-0001234-2020")
            assert result == County.LANCASTER


class TestCourtType:
    """Tests for the ``CourtType`` StrEnum."""

    class TestDocketPrefix:
        """Tests for the ``CourtType.docket_prefix`` property."""

        def test_magisterial_district_prefix(self) -> None:
            """``MAGISTERIAL_DISTRICT`` has prefix ``"MJ"``."""
            assert CourtType.MAGISTERIAL_DISTRICT.docket_prefix == "MJ"

        def test_municipal_court_prefix(self) -> None:
            """``MUNICIPAL_COURT`` has prefix ``"MC"``."""
            assert CourtType.MUNICIPAL_COURT.docket_prefix == "MC"

        def test_common_pleas_prefix(self) -> None:
            """``COMMON_PLEAS`` has prefix ``"CP"``."""
            assert CourtType.COMMON_PLEAS.docket_prefix == "CP"

    class TestFromDocketNumber:
        """Tests for ``CourtType.from_docket_number``."""

        def test_cp_docket_returns_common_pleas(self) -> None:
            """A ``CP-`` docket number maps to ``COMMON_PLEAS``."""
            result = CourtType.from_docket_number("CP-51-CR-0001234-2020")
            assert result == CourtType.COMMON_PLEAS

        def test_mc_docket_returns_municipal_court(self) -> None:
            """An ``MC-`` docket number maps to ``MUNICIPAL_COURT``."""
            result = CourtType.from_docket_number("MC-51-CR-0001234-2020")
            assert result == CourtType.MUNICIPAL_COURT

        def test_mj_docket_returns_magisterial_district(self) -> None:
            """An ``MJ-`` docket number maps to ``MAGISTERIAL_DISTRICT``."""
            result = CourtType.from_docket_number("MJ-01-CR-0001234-2020")
            assert result == CourtType.MAGISTERIAL_DISTRICT

        def test_unknown_prefix_returns_none(self) -> None:
            """An unrecognized prefix returns ``None``."""
            result = CourtType.from_docket_number("XX-51-CR-0001234-2020")
            assert result is None

        def test_returns_string_value(self) -> None:
            """The returned value is the string value of the enum, not the enum
            instance."""
            result = CourtType.from_docket_number("CP-51-CR-0001234-2020")
            assert isinstance(result, str)
            assert result == "Common Pleas"


class TestDocketType:
    """Tests for the ``DocketType`` StrEnum."""

    class TestDocketPrefix:
        """Tests for the ``DocketType.docket_prefix`` property."""

        def test_criminal_prefix(self) -> None:
            """``CRIMINAL`` has prefix ``"CR"``."""
            assert DocketType.CRIMINAL.docket_prefix == "CR"

        def test_civil_prefix(self) -> None:
            """``CIVIL`` has prefix ``"CV"``."""
            assert DocketType.CIVIL.docket_prefix == "CV"

        def test_traffic_prefix(self) -> None:
            """``TRAFFIC`` has prefix ``"TR"``."""
            assert DocketType.TRAFFIC.docket_prefix == "TR"

        def test_summary_prefix(self) -> None:
            """``SUMMARY`` has prefix ``"SU"``."""
            assert DocketType.SUMMARY.docket_prefix == "SU"

        def test_non_traffic_prefix(self) -> None:
            """``NON_TRAFFIC`` has prefix ``"NT"``."""
            assert DocketType.NON_TRAFFIC.docket_prefix == "NT"

        def test_landlord_tenant_prefix(self) -> None:
            """``LANDLORD_TENANT`` has prefix ``"LT"``."""
            assert DocketType.LANDLORD_TENANT.docket_prefix == "LT"

    class TestFromDocketNumber:
        """Tests for ``DocketType.from_docket_number``."""

        def test_criminal_docket_number(self) -> None:
            """A docket number containing ``-CR-`` maps to ``CRIMINAL``."""
            result = DocketType.from_docket_number("CP-51-CR-0001234-2020")
            assert result == DocketType.CRIMINAL

        def test_civil_docket_number(self) -> None:
            """A docket number containing ``-CV-`` maps to ``CIVIL``."""
            result = DocketType.from_docket_number("CP-51-CV-0001234-2020")
            assert result == DocketType.CIVIL

        def test_traffic_docket_number(self) -> None:
            """A docket number containing ``-TR-`` maps to ``TRAFFIC``."""
            result = DocketType.from_docket_number("MJ-01-TR-0001234-2020")
            assert result == DocketType.TRAFFIC

        def test_summary_docket_number(self) -> None:
            """A docket number containing ``-SU-`` maps to ``SUMMARY``."""
            result = DocketType.from_docket_number("MJ-01-SU-0001234-2020")
            assert result == DocketType.SUMMARY

        def test_unknown_type_returns_none(self) -> None:
            """A docket number with an unknown type segment returns ``None``."""
            result = DocketType.from_docket_number("CP-51-XX-0001234-2020")
            assert result is None

        def test_returns_string_value(self) -> None:
            """The returned value is the string value of the enum."""
            result = DocketType.from_docket_number("CP-51-CR-0001234-2020")
            assert isinstance(result, str)
            assert result == "Criminal"


class TestCaseStatus:
    """Tests for the ``CaseStatus`` StrEnum."""

    def test_active_value(self) -> None:
        """``ACTIVE`` has the expected string value."""
        assert CaseStatus.ACTIVE == "Active"

    def test_closed_value(self) -> None:
        """``CLOSED`` has the expected string value."""
        assert CaseStatus.CLOSED == "Closed"

    def test_sealed_value(self) -> None:
        """``SEALED`` has the expected string value."""
        assert CaseStatus.SEALED == "Sealed"

    def test_members_are_strings(self) -> None:
        """All members are instances of ``str``."""
        for member in CaseStatus:
            assert isinstance(member, str)


class TestSearchBy:
    """Tests for the ``SearchBy`` StrEnum."""

    def test_docket_number_value(self) -> None:
        """``DOCKET_NUMBER`` has the expected string value."""
        assert SearchBy.DOCKET_NUMBER == "DocketNumber"

    def test_participant_name_value(self) -> None:
        """``PARTICIPANT_NAME`` has the expected string value."""
        assert SearchBy.PARTICIPANT_NAME == "ParticipantName"

    def test_otn_value(self) -> None:
        """``OTN`` has the expected string value."""
        assert SearchBy.OTN == "OTN"

    def test_members_are_strings(self) -> None:
        """All members are instances of ``str``."""
        for member in SearchBy:
            assert isinstance(member, str)


class TestCountyMixin:
    """Tests for the ``CountyMixin`` model."""

    def test_county_defaults_to_none(self) -> None:
        """``county`` defaults to ``None`` when not provided."""

        class _M(CountyMixin):
            """Minimal concrete mixin model."""

        m = _M()
        assert m.county is None

    def test_county_accepts_county_name_alias(self) -> None:
        """``county`` can be set via the ``CountyName`` alias."""

        class _M(CountyMixin):
            """Minimal concrete mixin model."""

        m = _M(CountyName="Philadelphia")
        assert m.county == County.PHILADELPHIA

    def test_county_accepts_field_name(self) -> None:
        """``county`` can be set directly by field name."""

        class _M(CountyMixin):
            """Minimal concrete mixin model."""

        m = _M(county="Adams")
        assert m.county == County.ADAMS


class TestDocketNumberMixin:
    """Tests for the ``DocketNumberMixin`` model."""

    def test_docket_number_alias_accepted(self) -> None:
        """``docket_number`` can be set via the ``DocketNumber`` alias."""

        class _M(DocketNumberMixin):
            """Minimal concrete mixin model."""

        m = _M(DocketNumber="CP-51-CR-0001234-2020")
        assert m.docket_number == "CP-51-CR-0001234-2020"

    def test_docket_number_field_name_accepted(self) -> None:
        """``docket_number`` can be set by field name."""

        class _M(DocketNumberMixin):
            """Minimal concrete mixin model."""

        m = _M(docket_number="CP-51-CR-0001234-2020")
        assert m.docket_number == "CP-51-CR-0001234-2020"


class TestCaseStatusMixin:
    """Tests for the ``CaseStatusMixin`` model."""

    def test_case_status_defaults_to_none(self) -> None:
        """``case_status`` defaults to ``None`` when not provided."""

        class _M(CaseStatusMixin):
            """Minimal concrete mixin model."""

        m = _M()
        assert m.case_status is None

    def test_case_status_alias_accepted(self) -> None:
        """``case_status`` can be set via the ``CaseStatus`` alias."""

        class _M(CaseStatusMixin):
            """Minimal concrete mixin model."""

        m = _M(CaseStatus="Active")
        assert m.case_status == CaseStatus.ACTIVE


class TestOtnMixin:
    """Tests for the ``OtnMixin`` model."""

    def test_otn_defaults_to_none(self) -> None:
        """``otn`` defaults to ``None`` when not provided."""

        class _M(OtnMixin):
            """Minimal concrete mixin model."""

        m = _M()
        assert m.otn is None

    def test_otn_alias_accepted(self) -> None:
        """``otn`` can be set via the ``OTN`` alias."""

        class _M(OtnMixin):
            """Minimal concrete mixin model."""

        m = _M(OTN="T123456789")
        assert m.otn == "T123456789"


class TestCourtTypeMixin:
    """Tests for the ``CourtTypeMixin`` model."""

    def test_court_type_defaults_to_none(self) -> None:
        """``court_type`` defaults to ``None`` when not provided."""

        class _M(CourtTypeMixin):
            """Minimal concrete mixin model."""

        m = _M()
        assert m.court_type is None

    def test_court_type_alias_accepted(self) -> None:
        """``court_type`` can be set via the ``CourtSystem`` alias."""

        class _M(CourtTypeMixin):
            """Minimal concrete mixin model."""

        m = _M(CourtSystem="Common Pleas")
        assert m.court_type == CourtType.COMMON_PLEAS


class TestCaseTypeMixin:
    """Tests for the ``CaseTypeMixin`` model."""

    def test_docket_type_defaults_to_none(self) -> None:
        """``docket_type`` defaults to ``None`` when not provided."""

        class _M(CaseTypeMixin):
            """Minimal concrete mixin model."""

        m = _M()
        assert m.docket_type is None

    def test_docket_type_can_be_set(self) -> None:
        """``docket_type`` is stored when provided."""

        class _M(CaseTypeMixin):
            """Minimal concrete mixin model."""

        m = _M(docket_type="Criminal")
        assert m.docket_type == DocketType.CRIMINAL

    def test_inherits_court_type_from_mixin(self) -> None:
        """``CaseTypeMixin`` exposes ``court_type`` inherited from
        ``CourtTypeMixin``."""

        class _M(CaseTypeMixin):
            """Minimal concrete mixin model."""

        m = _M(CourtSystem="Municipal Court")
        assert m.court_type == CourtType.MUNICIPAL_COURT
