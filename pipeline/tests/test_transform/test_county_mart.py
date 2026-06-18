import polars as pl
import pytest

from urbanstack.config import Settings
from urbanstack.geography import DFW_COUNTY_FIPS, DFW_STATE_FIPS
from urbanstack.transform.county_mart import (
    _aggregate_epa_sld,
    _aggregate_fars,
    build_county_mart,
)


def _make_acs_df() -> pl.DataFrame:
    rows = []
    for name, fips in DFW_COUNTY_FIPS.items():
        rows.append(
            {
                "state_fips": DFW_STATE_FIPS,
                "county_fips": fips,
                "name": f"{name} County, Texas",
                "tract_fips": None,
                "block_group_fips": None,
                "total_population": 100_000,
                "per_capita_income": 30_000,
                "median_household_income": 60_000,
                "commute_drove_alone": 700,
                "commute_transit": 100,
                "commute_walked": 50,
                "commute_biked": 25,
                "commute_wfh": 125,
                "vehicles_available": 90_000,
                "median_rent": 1200,
                "median_home_value": 250_000,
            }
        )
    return pl.DataFrame(rows)


def _make_gazetteer_df() -> pl.DataFrame:
    rows = []
    for name, fips in DFW_COUNTY_FIPS.items():
        rows.append(
            {
                "county_fips": f"{DFW_STATE_FIPS}{fips}",
                "county_name": f"{name} County",
                "state_abbr": "TX",
                "land_area_sqm": 2_589_988_000,
                "water_area_sqm": 50_000_000,
                "latitude": 32.77,
                "longitude": -96.78,
            }
        )
    return pl.DataFrame(rows)


def _make_epa_sld_df() -> pl.DataFrame:
    rows = []
    for fips in DFW_COUNTY_FIPS.values():
        for bg in range(3):
            rows.append(
                {
                    "geoid": f"{DFW_STATE_FIPS}{fips}01010{bg}",
                    "state_fips": DFW_STATE_FIPS,
                    "county_fips": fips,
                    "tract_fips": "010100",
                    "cbsa": "19100",
                    "d1a": 5.0,
                    "d1b": 10.0 + bg,
                    "d1c": 8.0,
                    "d2a_jphh": 1.5,
                    "d2b_e8mixa": 0.8,
                    "d3b": 100.0 + bg * 10,
                    "d5dr": 0.4,
                    "d5de": 0.6,
                    "d4a": 300.0,
                    "d4d": 40.0 + bg * 5,
                    "nat_walk_ind": 12.0 + bg,
                    "pct_ao0": 0.10 + bg * 0.01,
                    "autoown": 1.8,
                }
            )
    return pl.DataFrame(rows)


def _make_fars_df() -> pl.DataFrame:
    rows = []
    case_id = 1000
    for fips in DFW_COUNTY_FIPS.values():
        for _ in range(2):
            case_id += 1
            rows.append(
                {
                    "case_id": case_id,
                    "state_fips": DFW_STATE_FIPS,
                    "county_fips": fips,
                    "year": 2022,
                    "month": 6,
                    "fatalities": 2,
                    "persons": 3,
                    "pedestrians": 1,
                    "drunk_drivers": 0,
                    "latitude": None,
                    "longitude": None,
                }
            )
    return pl.DataFrame(rows)


def _make_usaspending_df() -> pl.DataFrame:
    rows = []
    for fips in DFW_COUNTY_FIPS.values():
        rows.append(
            {
                "county_fips": f"{DFW_STATE_FIPS}{fips}",
                "county_name": "Test County",
                "total_obligation": 1_000_000.0,
                "per_capita": 10.0,
                "population": 100_000,
                "fiscal_year_start": "2020-10-01",
                "fiscal_year_end": "2024-09-30",
            }
        )
    return pl.DataFrame(rows)


def _write_staging(settings: Settings) -> None:
    for name, df_fn in [
        ("acs/acs_county_2023.parquet", _make_acs_df),
        ("gazetteer/gazetteer_dfw.parquet", _make_gazetteer_df),
        ("epa_sld/epa_sld_dfw.parquet", _make_epa_sld_df),
        ("fars/fars_dfw_2015_2022.parquet", _make_fars_df),
        ("usaspending/usaspending_dfw_2020_2024.parquet", _make_usaspending_df),
    ]:
        path = settings.staging_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        df_fn().write_parquet(path)


def test_full_join_county_count(settings: Settings) -> None:
    _write_staging(settings)
    df = build_county_mart(settings, force=True)
    assert len(df) == 12


def test_commute_percentages(settings: Settings) -> None:
    _write_staging(settings)
    df = build_county_mart(settings, force=True)
    row = df.to_dicts()[0]
    total = 700 + 100 + 50 + 25 + 125
    assert abs(row["pct_drove_alone"] - 700 / total) < 0.001
    assert abs(row["pct_transit"] - 100 / total) < 0.001
    assert abs(row["pct_wfh"] - 125 / total) < 0.001


def test_epa_sld_aggregation() -> None:
    epa = _make_epa_sld_df()
    agg = _aggregate_epa_sld(epa)
    assert len(agg) == 12
    row = agg.filter(pl.col("county_fips") == "48113").to_dicts()[0]
    assert abs(row["avg_walkability"] - 13.0) < 0.01
    assert abs(row["avg_pop_density"] - 11.0) < 0.01


def test_fars_aggregation() -> None:
    fars = _make_fars_df()
    agg = _aggregate_fars(fars)
    assert len(agg) == 12
    row = agg.filter(pl.col("county_fips") == "48113").to_dicts()[0]
    assert row["total_fatalities"] == 4
    assert row["total_crashes"] == 2
    assert row["pedestrian_involved_crashes"] == 2


def test_graceful_missing_sources(settings: Settings) -> None:
    acs_dir = settings.staging_dir / "acs"
    acs_dir.mkdir(parents=True, exist_ok=True)
    _make_acs_df().write_parquet(acs_dir / "acs_county_2023.parquet")

    df = build_county_mart(settings, force=True)
    assert len(df) == 12
    assert "pop_density_sqmi" in df.columns
    assert df["pop_density_sqmi"][0] is None


def test_raises_without_acs(settings: Settings) -> None:
    with pytest.raises(FileNotFoundError, match="ACS"):
        build_county_mart(settings, force=True)


def test_idempotent_skip(settings: Settings) -> None:
    settings.marts_dir.mkdir(parents=True, exist_ok=True)
    mart_path = settings.marts_dir / "county_summary.parquet"
    existing = pl.DataFrame({"county_fips": ["48113"]})
    existing.write_parquet(mart_path)

    df = build_county_mart(settings)
    assert len(df) == 1


def test_pop_density_computed(settings: Settings) -> None:
    _write_staging(settings)
    df = build_county_mart(settings, force=True)
    row = df.to_dicts()[0]
    land_sqmi = 2_589_988_000 / 2_589_988.0
    expected_density = 100_000 / land_sqmi
    assert abs(row["pop_density_sqmi"] - expected_density) < 0.01
