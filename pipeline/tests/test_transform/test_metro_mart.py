import polars as pl

from urbanstack.config import Settings
from urbanstack.geography import DFW_COUNTY_FIPS, DFW_STATE_FIPS
from urbanstack.transform.metro_mart import METRO_FIPS, METRO_NAME, build_metro_mart


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
                    "d1b": 10.0,
                    "d1c": 8.0,
                    "d2a_jphh": 1.5,
                    "d2b_e8mixa": 0.8,
                    "d3b": 100.0,
                    "d5dr": 0.4,
                    "d5de": 0.6,
                    "d4a": 300.0,
                    "d4d": 40.0,
                    "nat_walk_ind": 12.0,
                    "pct_ao0": 0.10,
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


def test_metro_mart_single_row(settings: Settings) -> None:
    _write_staging(settings)
    df = build_metro_mart(settings, force=True)
    assert len(df) == 1


def test_metro_mart_identifier(settings: Settings) -> None:
    _write_staging(settings)
    df = build_metro_mart(settings, force=True)
    row = df.to_dicts()[0]
    assert row["county_fips"] == METRO_FIPS
    assert row["county_name"] == METRO_NAME


def test_metro_mart_population_sum(settings: Settings) -> None:
    _write_staging(settings)
    df = build_metro_mart(settings, force=True)
    row = df.to_dicts()[0]
    assert row["population"] == 100_000 * 12


def test_metro_mart_weighted_income(settings: Settings) -> None:
    _write_staging(settings)
    df = build_metro_mart(settings, force=True)
    row = df.to_dicts()[0]
    assert abs(row["per_capita_income"] - 30_000) < 1.0


def test_metro_mart_safety_sums(settings: Settings) -> None:
    _write_staging(settings)
    df = build_metro_mart(settings, force=True)
    row = df.to_dicts()[0]
    assert row["total_fatalities"] == 2 * 2 * 12
    assert row["total_crashes"] == 2 * 12


def test_metro_mart_federal_spending(settings: Settings) -> None:
    _write_staging(settings)
    df = build_metro_mart(settings, force=True)
    row = df.to_dicts()[0]
    assert row["federal_obligation"] == 1_000_000.0 * 12
    expected_per_capita = (1_000_000.0 * 12) / (100_000 * 12)
    assert abs(row["federal_per_capita"] - expected_per_capita) < 0.01


def test_idempotent_skip(settings: Settings) -> None:
    settings.marts_dir.mkdir(parents=True, exist_ok=True)
    mart_path = settings.marts_dir / "metro_summary.parquet"
    existing = pl.DataFrame({"county_fips": [METRO_FIPS]})
    existing.write_parquet(mart_path)

    df = build_metro_mart(settings)
    assert len(df) == 1
