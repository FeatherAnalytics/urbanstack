from urbanstack.metro import CHICAGO, DFW, FIPS_TO_ABBR, get_metro

import pytest


def test_dfw_single_state() -> None:
    assert len(DFW.states) == 1
    assert DFW.state_fips_set == {"48"}
    assert DFW.state_fips_int_set == {48}


def test_dfw_county_fips_5_prefixed() -> None:
    for fips_5 in DFW.county_fips_5_set:
        assert fips_5.startswith("48")
        assert len(fips_5) == 5


def test_chicago_multi_state() -> None:
    assert len(CHICAGO.states) == 3
    assert CHICAGO.state_fips_set == {"17", "18", "55"}
    assert CHICAGO.state_fips_int_set == {17, 18, 55}


def test_chicago_counties_across_states() -> None:
    fips_5 = CHICAGO.county_fips_5_set
    assert "17031" in fips_5  # Cook County, IL
    assert "18089" in fips_5  # Lake County, IN
    assert "55059" in fips_5  # Kenosha County, WI


def test_chicago_county_count() -> None:
    total = sum(len(c) for c in CHICAGO.states.values())
    assert total == 14  # 9 IL + 4 IN + 1 WI


def test_fips_to_abbr_coverage() -> None:
    for metro in [DFW, CHICAGO]:
        for state_fips in metro.state_fips_set:
            assert state_fips in FIPS_TO_ABBR


def test_get_metro_valid() -> None:
    assert get_metro("dfw") is DFW
    assert get_metro("chicago") is CHICAGO


def test_get_metro_invalid() -> None:
    with pytest.raises(KeyError, match="Unknown metro"):
        get_metro("bogus")
