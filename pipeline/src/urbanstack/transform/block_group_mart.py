import json
import logging
from pathlib import Path

import polars as pl

from urbanstack.config import Settings
from urbanstack.extract.acs import extract_acs
from urbanstack.geography import DFW_STATE_FIPS
from urbanstack.transform.derived import apply_derived_metrics
from urbanstack.transform.spatial import assign_points_to_areas, load_boundaries
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


def _infer_ridership(base: pl.DataFrame, ntd: pl.DataFrame) -> pl.DataFrame:
    full_years = (
        ntd.group_by("year")
        .agg(pl.col("month").n_unique().alias("n_months"))
        .filter(pl.col("n_months") >= 12)
        .sort("year", descending=True)
    )
    if full_years.is_empty():
        logger.warning("NTD: no year with 12 months of data")
        return base.with_columns(
            pl.lit(None).cast(pl.Int64).alias("total_annual_ridership"),
            pl.lit(None).cast(pl.Float64).alias("ridership_per_capita"),
        )

    latest_year = full_years["year"][0]
    year_data = ntd.filter(pl.col("year") == latest_year)
    metro_total_ridership = year_data.select(pl.col("unlinked_passenger_trips").sum()).item()

    base = base.with_columns(
        (pl.col("pct_transit") * pl.col("total_commuters")).alias("_bg_transit_commuters"),
    )
    metro_transit_commuters = base.select(pl.col("_bg_transit_commuters").sum()).item()

    if not metro_transit_commuters or metro_transit_commuters == 0:
        return base.drop("_bg_transit_commuters").with_columns(
            pl.lit(None).cast(pl.Int64).alias("total_annual_ridership"),
            pl.lit(None).cast(pl.Float64).alias("ridership_per_capita"),
        )

    base = base.with_columns(
        (
            pl.lit(metro_total_ridership)
            * (pl.col("_bg_transit_commuters") / pl.lit(metro_transit_commuters))
        )
        .cast(pl.Int64)
        .alias("total_annual_ridership"),
    )
    base = base.with_columns(
        (
            pl.col("total_annual_ridership").cast(pl.Float64)
            / pl.col("total_population").cast(pl.Float64)
        ).alias("ridership_per_capita"),
    )
    return base.drop("_bg_transit_commuters")


def _infer_congestion(base: pl.DataFrame, umr: pl.DataFrame) -> pl.DataFrame:
    latest = umr.sort("year", descending=True).head(1).to_dicts()[0]
    delay_per = latest.get("annual_delay_per_commuter")
    cost_per = latest.get("congestion_cost_per_commuter")

    base = base.with_columns(
        (pl.col("pct_drove_alone") * pl.col("total_commuters")).alias("_bg_auto_commuters"),
    )
    base = base.with_columns(
        (pl.lit(delay_per) * pl.col("_bg_auto_commuters")).cast(pl.Float64).alias("total_delay_hours"),
        (pl.lit(cost_per) * pl.col("_bg_auto_commuters")).cast(pl.Float64).alias("total_congestion_cost"),
    )
    base = base.with_columns(
        (pl.col("total_delay_hours") / pl.col("total_population").cast(pl.Float64)).alias("delay_per_capita"),
        (pl.col("total_congestion_cost") / pl.col("total_population").cast(pl.Float64)).alias("congestion_cost_per_capita"),
    )
    return base.drop("_bg_auto_commuters")


def _aggregate_fars_to_block_groups(
    fars: pl.DataFrame, geojson_path: Path
) -> pl.DataFrame:
    """Spatial-join FARS crashes to block groups and aggregate."""
    valid = fars.filter(
        pl.col("latitude").is_not_null() & pl.col("longitude").is_not_null()
    )
    logger.info("FARS: %d crashes with valid coords (of %d)", len(valid), len(fars))

    boundaries = load_boundaries(geojson_path)
    joined = assign_points_to_areas(valid, boundaries)
    matched = joined.filter(pl.col("area_id").is_not_null())
    logger.info("FARS: %d crashes matched to block groups", len(matched))

    return (
        matched.group_by("area_id")
        .agg(
            pl.col("fatalities").sum().alias("total_fatalities"),
            pl.len().alias("total_crashes"),
            (pl.col("pedestrians") > 0).sum().cast(pl.Int64).alias("pedestrian_involved_crashes"),
            (pl.col("drunk_drivers") > 0).sum().cast(pl.Int64).alias("drunk_driver_crashes"),
        )
        .rename({"area_id": "geoid_12"})
    )


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

    umr_path = settings.staging_dir / "umr" / "umr_dfw.parquet"
    if umr_path.exists():
        umr = pl.read_parquet(umr_path)
        base = _infer_congestion(base, umr)
    else:
        logger.warning("UMR missing — congestion columns will be null")
        base = base.with_columns(
            pl.lit(None).cast(pl.Float64).alias("total_delay_hours"),
            pl.lit(None).cast(pl.Float64).alias("total_congestion_cost"),
            pl.lit(None).cast(pl.Float64).alias("delay_per_capita"),
            pl.lit(None).cast(pl.Float64).alias("congestion_cost_per_capita"),
        )

    ntd_path = find_parquet(settings.staging_dir / "ntd")
    if ntd_path:
        ntd = pl.read_parquet(ntd_path)
        base = _infer_ridership(base, ntd)
    else:
        logger.warning("NTD missing — ridership columns will be null")
        base = base.with_columns(
            pl.lit(None).cast(pl.Int64).alias("total_annual_ridership"),
            pl.lit(None).cast(pl.Float64).alias("ridership_per_capita"),
        )

    geojson_path = (
        Path(settings.data_dir).resolve().parent.parent
        / "web" / "public" / "data" / "dfw_block_groups.geojson"
    )
    fars_path = find_parquet(settings.staging_dir / "fars")
    if fars_path and fars_path.exists() and geojson_path.exists():
        fars = pl.read_parquet(fars_path)
        fars_agg = _aggregate_fars_to_block_groups(fars, geojson_path)
        base = base.join(fars_agg, on="geoid_12", how="left")
    else:
        logger.warning("FARS or block group GeoJSON missing — crash columns will be null")

    # Block groups with no FARS crashes should be 0, not null
    safety_cols = ["total_fatalities", "total_crashes", "pedestrian_involved_crashes", "drunk_driver_crashes"]
    base = base.with_columns([pl.col(c).fill_null(0) for c in safety_cols if c in base.columns])

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

    base = apply_derived_metrics(base, granularity="block_group")

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
    for r in records:
        for k, v in r.items():
            if isinstance(v, float) and (v != v or v == float("inf") or v == float("-inf")):
                r[k] = None
    json_path.write_text(json.dumps(records, default=str))
    logger.info("Wrote block group JSON: %d rows to %s", len(records), json_path)

    return base
