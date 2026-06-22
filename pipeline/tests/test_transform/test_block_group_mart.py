from pathlib import Path

import polars as pl
import pytest

from urbanstack.config import Settings
from urbanstack.metro import DFW, MetroConfig
from urbanstack.transform.block_group_mart import (
    _build_acs_base,
    _join_epa_sld,
    build_block_group_mart,
)


def _make_bg_acs_df() -> pl.DataFrame:
    rows = []
    for name, fips in DFW.states["48"].items():
        for bg in range(1, 4):
            rows.append(
                {
                    "state_fips": "48",
                    "county_fips": fips,
                    "name": f"Block Group {bg}, Tract 0101, {name} County, Texas",
                    "tract_fips": "010100",
                    "block_group_fips": str(bg),
                    "total_population": 1000 + bg * 100,
                    "per_capita_income": 30_000,
                    "median_household_income": 60_000,
                    "commute_drove_alone": 70,
                    "commute_transit": 10,
                    "commute_walked": 5,
                    "commute_biked": 3,
                    "commute_wfh": 12,
                    "vehicles_available": 900,
                    "median_rent": 1200,
                    "median_home_value": 250_000,
                }
            )
    return pl.DataFrame(rows)


def _make_epa_sld_df() -> pl.DataFrame:
    rows = []
    for fips in DFW.states["48"].values():
        for bg in range(1, 4):
            rows.append(
                {
                    "geoid": f"48{fips}010100{bg}",
                    "state_fips": "48",
                    "county_fips": fips,
                    "tract_fips": "010100",
                    "cbsa": "19100",
                    "d1a": 5.0,
                    "d1b": 10.0 + bg,
                    "d1c": 8.0,
                    "d2a_jphh": 1.5,
                    "d2b_e8mixa": 0.8,
                    "d3b": 100.0,
                    "d5dr": 0.4,
                    "d5de": 0.6,
                    "d4a": 300.0,
                    "d4d": 40.0 + bg,
                    "nat_walk_ind": 12.0 + bg,
                    "pct_ao0": 0.10,
                    "autoown": 1.8,
                }
            )
    return pl.DataFrame(rows)


def _write_staging(settings: Settings) -> None:
    staging = settings.metro_staging_dir("dfw")
    acs_dir = staging / "acs"
    acs_dir.mkdir(parents=True, exist_ok=True)
    _make_bg_acs_df().write_parquet(acs_dir / "acs_block_group_2023.parquet")

    epa_dir = staging / "epa_sld"
    epa_dir.mkdir(parents=True, exist_ok=True)
    _make_epa_sld_df().write_parquet(epa_dir / "epa_sld_dfw.parquet")


def test_acs_base_geoid_construction() -> None:
    acs = _make_bg_acs_df()
    base = _build_acs_base(acs)
    assert "geoid_12" in base.columns
    row = base.to_dicts()[0]
    assert len(row["geoid_12"]) == 12


def test_acs_base_commute_percentages() -> None:
    acs = _make_bg_acs_df()
    base = _build_acs_base(acs)
    row = base.to_dicts()[0]
    total = 70 + 10 + 5 + 3 + 12
    assert abs(row["pct_drove_alone"] - 70 / total) < 0.001
    assert abs(row["pct_transit"] - 10 / total) < 0.001


def test_epa_sld_join() -> None:
    acs = _make_bg_acs_df()
    base = _build_acs_base(acs)
    epa = _make_epa_sld_df()
    joined = _join_epa_sld(base, epa)
    assert "avg_walkability" in joined.columns
    assert "avg_transit_frequency" in joined.columns
    row = joined.filter(pl.col("geoid_12") == "481130101001").to_dicts()
    assert len(row) == 1
    assert abs(row[0]["avg_walkability"] - 13.0) < 0.01


def test_full_build_row_count(settings: Settings, metro: MetroConfig) -> None:
    _write_staging(settings)
    df = build_block_group_mart(settings, metro, force=True)
    assert len(df) == 36  # 12 counties * 3 block groups each


def test_null_columns_present(settings: Settings, metro: MetroConfig) -> None:
    _write_staging(settings)
    df = build_block_group_mart(settings, metro, force=True)
    for col in ["total_fatalities", "federal_obligation", "pop_density_sqmi"]:
        assert col in df.columns
        assert df[col][0] is None


def test_idempotent_skip(settings: Settings, metro: MetroConfig) -> None:
    mart_dir = settings.metro_marts_dir("dfw")
    mart_dir.mkdir(parents=True, exist_ok=True)
    mart_path = mart_dir / "block_group_summary.parquet"
    existing = pl.DataFrame({"county_fips": ["481130101001"]})
    existing.write_parquet(mart_path)

    df = build_block_group_mart(settings, metro)
    assert len(df) == 1


def test_raises_without_api_key() -> None:
    no_key_settings = Settings(census_api_key="", data_dir=Path("/tmp/nonexistent"))
    with pytest.raises(ValueError, match="CENSUS_API_KEY"):
        build_block_group_mart(no_key_settings, DFW, force=True)
