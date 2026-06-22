from pathlib import Path
from unittest.mock import MagicMock, patch

import polars as pl
import pytest

from urbanstack.config import Settings
from urbanstack.extract.acs import ACS_VARIABLES, extract_acs
from urbanstack.metro import MetroConfig

VARIABLE_CODES = list(ACS_VARIABLES.keys())

COUNTY_HEADERS = ["NAME", *VARIABLE_CODES, "state", "county"]

COUNTY_ROW = [
    "Dallas County, Texas",
    "2613539",  # total_population
    "32585",  # per_capita_income
    "54747",  # median_household_income
    "900000",  # commute_drove_alone
    "50000",  # commute_transit
    "20000",  # commute_walked
    "5000",  # commute_biked
    "100000",  # commute_wfh
    "800000",  # vehicles_available
    "1200",  # median_rent
    "250000",  # median_home_value
    "48",
    "113",
]

BG_HEADERS = ["NAME", *VARIABLE_CODES, "state", "county", "tract", "block group"]

BG_ROW = [
    "Block Group 1, Census Tract 19.01, Dallas County, Texas",
    "1500",
    "28000",
    "50000",
    "800",
    "100",
    "50",
    "10",
    "200",
    "600",
    "1100",
    "220000",
    "48",
    "113",
    "019100",
    "1",
]


def _mock_county_response() -> list[list[str]]:
    return [COUNTY_HEADERS, COUNTY_ROW]


def _mock_bg_response() -> list[list[str]]:
    return [BG_HEADERS, BG_ROW]


def test_extract_county(settings: Settings, metro: MetroConfig) -> None:
    mock_resp = MagicMock()
    mock_resp.json.return_value = _mock_county_response()
    mock_resp.raise_for_status = MagicMock()

    with patch("urbanstack.extract.acs.requests.get", return_value=mock_resp):
        df = extract_acs(settings, metro, granularity="county", year=2023)

    assert isinstance(df, pl.DataFrame)
    assert len(df) == 1
    assert "state_fips" in df.columns
    assert "county_fips" in df.columns
    assert "total_population" in df.columns
    assert df["total_population"][0] == 2613539
    assert df["tract_fips"][0] is None


def test_extract_block_group(settings: Settings, metro: MetroConfig) -> None:
    mock_resp = MagicMock()
    mock_resp.json.return_value = _mock_bg_response()
    mock_resp.raise_for_status = MagicMock()

    with patch("urbanstack.extract.acs.requests.get", return_value=mock_resp) as mock_get:
        df = extract_acs(settings, metro, granularity="block_group", year=2023)

    assert mock_get.call_count == sum(len(c) for c in metro.states.values())

    # Verify first call uses separate "in" tuples (not combined string)
    first_call_params = mock_get.call_args_list[0]
    _, first_kwargs = first_call_params
    positional = first_call_params[0]
    params = first_kwargs.get("params", positional[1] if len(positional) > 1 else None)
    assert isinstance(params, list), "Block group params should be a list of tuples"
    in_tuples = [t for t in params if t[0] == "in"]
    assert len(in_tuples) == 2, "Should have two separate 'in' params"
    # DFW is single-state, so just use "48"
    assert ("in", "state:48") in in_tuples

    assert isinstance(df, pl.DataFrame)
    assert len(df) >= 1
    assert df["tract_fips"][0] == "019100"
    assert df["block_group_fips"][0] == "1"
    fips_val = (
        df["state_fips"][0]
        + df["county_fips"][0]
        + df["tract_fips"][0]
        + df["block_group_fips"][0]
    )
    assert fips_val == "481130191001"


def test_suppressed_values_become_null(settings: Settings, metro: MetroConfig) -> None:
    suppressed_row = list(COUNTY_ROW)
    suppressed_row[COUNTY_HEADERS.index("B25077_001E")] = "-666666666"

    mock_resp = MagicMock()
    mock_resp.json.return_value = [COUNTY_HEADERS, suppressed_row]
    mock_resp.raise_for_status = MagicMock()

    with patch("urbanstack.extract.acs.requests.get", return_value=mock_resp):
        df = extract_acs(settings, metro, granularity="county", year=2023)

    assert df["median_home_value"][0] is None


def test_idempotent_skip(settings: Settings, metro: MetroConfig) -> None:
    parquet_dir = settings.metro_staging_dir(metro.metro_id) / "acs"
    parquet_dir.mkdir(parents=True, exist_ok=True)
    parquet_path = parquet_dir / "acs_county_2023.parquet"
    existing = pl.DataFrame({"state_fips": ["48"], "county_fips": ["113"]})
    existing.write_parquet(parquet_path)

    with patch("urbanstack.extract.acs.requests.get") as mock_get:
        df = extract_acs(settings, metro, granularity="county", year=2023)
        mock_get.assert_not_called()

    assert len(df) == 1


def test_null_census_value_becomes_none(settings: Settings, metro: MetroConfig) -> None:
    """Census API can return JSON null for some variables."""
    null_row = list(COUNTY_ROW)
    null_row[COUNTY_HEADERS.index("B25064_001E")] = None  # type: ignore[call-overload]

    mock_resp = MagicMock()
    mock_resp.json.return_value = [COUNTY_HEADERS, null_row]
    mock_resp.raise_for_status = MagicMock()

    with patch("urbanstack.extract.acs.requests.get", return_value=mock_resp):
        df = extract_acs(settings, metro, granularity="county", year=2023)

    assert df["median_rent"][0] is None


def test_empty_string_census_value_becomes_none(settings: Settings, metro: MetroConfig) -> None:
    """Census API can return empty strings for some variables."""
    empty_row = list(COUNTY_ROW)
    empty_row[COUNTY_HEADERS.index("B25064_001E")] = ""

    mock_resp = MagicMock()
    mock_resp.json.return_value = [COUNTY_HEADERS, empty_row]
    mock_resp.raise_for_status = MagicMock()

    with patch("urbanstack.extract.acs.requests.get", return_value=mock_resp):
        df = extract_acs(settings, metro, granularity="county", year=2023)

    assert df["median_rent"][0] is None


def test_missing_api_key_raises(tmp_path: Path, metro: MetroConfig) -> None:
    s = Settings(census_api_key="", data_dir=tmp_path)
    with pytest.raises(ValueError, match="CENSUS_API_KEY"):
        extract_acs(s, metro)
