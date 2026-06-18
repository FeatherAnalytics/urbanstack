import json
import logging
from pathlib import Path

import polars as pl

from urbanstack.config import Settings
from urbanstack.extract.acs import extract_acs
from urbanstack.geography import DFW_STATE_FIPS
from urbanstack.utils import find_parquet

logger = logging.getLogger(__name__)


def _build_acs_base(acs: pl.DataFrame) -> pl.DataFrame:
    df = acs.with_columns(
        (
            pl.col("state_fips")
            + pl.col("county_fips")
            + pl.col("tract_fips")
            + pl.col("block_group_fips")
        ).alias("geoid_12"),
        (pl.col("state_fips") + pl.col("county_fips")).alias("county_fips_5"),
    )

    commute_cols = [
        "commute_drove_alone",
        "commute_transit",
        "commute_walked",
        "commute_biked",
        "commute_wfh",
    ]

    df = df.with_columns(
        pl.sum_horizontal([pl.col(c).fill_null(0) for c in commute_cols]).alias(
            "total_commuters"
        ),
    )

    for col in commute_cols:
        pct_name = f"pct_{col.removeprefix('commute_')}"
        df = df.with_columns(
            pl.when(pl.col("total_commuters") > 0)
            .then(
                pl.col(col).cast(pl.Float64)
                / pl.col("total_commuters").cast(pl.Float64)
            )
            .otherwise(None)
            .alias(pct_name),
        )

    keep = [
        "geoid_12",
        "county_fips_5",
        "name",
        "total_population",
        "per_capita_income",
        "median_household_income",
        "median_rent",
        "median_home_value",
        "vehicles_available",
        "total_commuters",
        "pct_drove_alone",
        "pct_transit",
        "pct_walked",
        "pct_biked",
        "pct_wfh",
    ]

    return df.select(keep)


def _join_epa_sld(base: pl.DataFrame, epa: pl.DataFrame) -> pl.DataFrame:
    epa_cols = epa.select(
        pl.col("geoid"),
        pl.col("nat_walk_ind").alias("avg_walkability"),
        pl.col("d1b").alias("avg_pop_density"),
        pl.col("d1c").alias("avg_job_density"),
        pl.col("d3b").alias("avg_intersection_density"),
        pl.col("d4d").alias("avg_transit_frequency"),
        pl.col("pct_ao0").alias("pct_zero_car_hh"),
    )
    return base.join(epa_cols, left_on="geoid_12", right_on="geoid", how="left")


def build_block_group_mart(
    settings: Settings, *, force: bool = False
) -> pl.DataFrame:
    mart_path = settings.marts_dir / "block_group_summary.parquet"

    if mart_path.exists() and not force:
        logger.info("Mart exists, skipping: %s", mart_path)
        return pl.read_parquet(mart_path)

    acs = extract_acs(settings, granularity="block_group")
    acs = acs.filter(pl.col("state_fips") == DFW_STATE_FIPS)
    acs = acs.filter(pl.col("tract_fips").is_not_null())

    base = _build_acs_base(acs)

    epa_path = find_parquet(settings.staging_dir / "epa_sld")
    if epa_path and epa_path.exists():
        epa = pl.read_parquet(epa_path)
        base = _join_epa_sld(base, epa)
    else:
        logger.warning("EPA SLD missing — walkability columns will be null")

    null_cols = {
        "total_fatalities": pl.Int64,
        "total_crashes": pl.Int64,
        "pedestrian_involved_crashes": pl.Int64,
        "drunk_driver_crashes": pl.Int64,
        "federal_obligation": pl.Float64,
        "federal_per_capita": pl.Float64,
        "land_area_sqm": pl.Int64,
        "water_area_sqm": pl.Int64,
        "land_area_sqmi": pl.Float64,
        "latitude": pl.Float64,
        "longitude": pl.Float64,
        "pop_density_sqmi": pl.Float64,
        "travel_time_index": pl.Float64,
        "planning_time_index": pl.Float64,
        "annual_delay_hours": pl.Float64,
        "congestion_cost": pl.Float64,
    }
    missing = {
        name: pl.lit(None).cast(dtype)
        for name, dtype in null_cols.items()
        if name not in base.columns
    }
    if missing:
        base = base.with_columns(**missing)

    base = base.rename(
        {
            "geoid_12": "county_fips",
            "total_population": "population",
            "name": "county_name",
        }
    )

    settings.marts_dir.mkdir(parents=True, exist_ok=True)
    base.write_parquet(mart_path)
    logger.info(
        "Wrote block group mart: %d rows to %s", len(base), mart_path
    )

    json_path = (
        Path(settings.data_dir).resolve().parent.parent
        / "web" / "public" / "data" / "block_group_summary.json"
    )
    json_path.parent.mkdir(parents=True, exist_ok=True)
    records = base.to_dicts()
    json_path.write_text(json.dumps(records, default=str))
    logger.info("Wrote block group JSON: %d rows to %s", len(records), json_path)

    return base
