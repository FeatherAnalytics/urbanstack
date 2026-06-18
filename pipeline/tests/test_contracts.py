import pytest
from pydantic import ValidationError

from urbanstack.contracts.acs import AcsRecord


def _county_kwargs() -> dict:
    return {
        "state_fips": "48",
        "county_fips": "113",
        "name": "Dallas County, Texas",
        "total_population": 2613539,
        "per_capita_income": 32585,
        "median_household_income": 54747,
        "commute_drove_alone": 900000,
        "commute_transit": 50000,
        "commute_walked": 20000,
        "commute_biked": 5000,
        "commute_wfh": 100000,
        "vehicles_available": 800000,
        "median_rent": 1200,
        "median_home_value": 250000,
    }


def test_valid_county_record() -> None:
    record = AcsRecord(**_county_kwargs())
    assert record.fips == "48113"


def test_valid_block_group_record() -> None:
    kwargs = _county_kwargs()
    kwargs["tract_fips"] = "019100"
    kwargs["block_group_fips"] = "1"
    record = AcsRecord(**kwargs)
    assert record.fips == "481130191001"


def test_invalid_fips_length() -> None:
    kwargs = _county_kwargs()
    kwargs["state_fips"] = "4"
    with pytest.raises(ValidationError):
        AcsRecord(**kwargs)


def test_negative_population_rejected() -> None:
    kwargs = _county_kwargs()
    kwargs["total_population"] = -1
    with pytest.raises(ValidationError):
        AcsRecord(**kwargs)


def test_tract_only_fips() -> None:
    """Tract-level FIPS should include tract even without block group."""
    kwargs = _county_kwargs()
    kwargs["tract_fips"] = "019100"
    record = AcsRecord(**kwargs)
    assert record.fips == "48113019100"


def test_null_values_accepted() -> None:
    record = AcsRecord(
        state_fips="48",
        county_fips="113",
        name="Dallas County, Texas",
        total_population=None,
        median_home_value=None,
    )
    assert record.total_population is None
    assert record.median_home_value is None
