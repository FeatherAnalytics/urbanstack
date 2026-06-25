import json
import logging

import polars as pl

from urbanstack.config import Settings
from urbanstack.extract.acs import extract_acs
from urbanstack.metro import METRO_REGISTRY, MetroConfig
from urbanstack.transform._shared import infer_congestion, infer_ridership, sanitize_records
from urbanstack.transform.derived import apply_derived_metrics
from urbanstack.transform.spatial import (
    assign_points_to_areas,
    compute_centroids,
    compute_amenity_proximity,
    load_boundaries,
)
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


def _aggregate_fars_to_block_groups(
    fars: pl.DataFrame,
    boundaries: list[tuple[str, list[list[list[float]]]]],
) -> pl.DataFrame:
    """Spatial-join FARS crashes to block groups and aggregate."""
    valid = fars.filter(
        pl.col("latitude").is_not_null() & pl.col("longitude").is_not_null()
    )
    logger.info("FARS: %d crashes with valid coords (of %d)", len(valid), len(fars))

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


def build_national_block_group_mart(
    settings: Settings, *, force: bool = False
) -> pl.DataFrame:
    """Build block group mart from national ACS data (no metro dependency)."""
    mart_dir = settings.exports_dir
    mart_path = mart_dir / "block_groups.parquet"

    if mart_path.exists() and not force:
        logger.info("National mart exists, skipping: %s", mart_path)
        return pl.read_parquet(mart_path)

    acs_path = settings.staging_dir / "national" / "acs" / "acs_block_group_2023.parquet"
    if not acs_path.exists():
        raise FileNotFoundError(f"National ACS not found: {acs_path}. Run `urbanstack extract-national` first.")

    acs = pl.read_parquet(acs_path)
    acs = acs.filter(pl.col("tract_fips").is_not_null())
    logger.info("National ACS: %d block groups", len(acs))

    base = _build_acs_base(acs)

    # yagni: national EPA SLD, FARS, NTD, UMR joins deferred — add when sources extracted nationally
    null_cols = {
        "avg_walkability": pl.Float64,
        "avg_pop_density": pl.Float64,
        "avg_job_density": pl.Float64,
        "avg_intersection_density": pl.Float64,
        "avg_transit_frequency": pl.Float64,
        "pct_zero_car_hh": pl.Float64,
        "total_delay_hours": pl.Float64,
        "total_congestion_cost": pl.Float64,
        "delay_per_capita": pl.Float64,
        "congestion_cost_per_capita": pl.Float64,
        "total_annual_ridership": pl.Int64,
        "ridership_per_capita": pl.Float64,
        "total_fatalities": pl.Int64,
        "total_crashes": pl.Int64,
        "pedestrian_involved_crashes": pl.Int64,
        "drunk_driver_crashes": pl.Int64,
        "fatalities_per_capita": pl.Float64,
        "crashes_per_capita": pl.Float64,
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

    base = base.rename({
        "geoid_12": "county_fips",
        "total_population": "population",
        "name": "county_name",
    })

    base = apply_derived_metrics(base, granularity="block_group")

    # Map county_fips_5 to metro_id for known metros
    fips_to_metro: dict[str, str] = {}
    for metro_id, metro in METRO_REGISTRY.items():
        for fips5 in metro.county_fips_5_set:
            fips_to_metro[fips5] = metro_id
    base = base.with_columns(
        pl.col("county_fips_5").replace_strict(fips_to_metro, default=None).alias("metro_id")
    )

    mart_dir.mkdir(parents=True, exist_ok=True)
    base.write_parquet(mart_path)
    logger.info("National block group mart: %d rows, %.1f MB → %s", len(base), mart_path.stat().st_size / 1e6, mart_path)

    return base


def build_block_group_mart(
    settings: Settings, metro: MetroConfig, *, force: bool = False
) -> pl.DataFrame:
    staging = settings.metro_staging_dir(metro.metro_id)
    mart_path = settings.metro_marts_dir(metro.metro_id) / "block_group_summary.parquet"

    if mart_path.exists() and not force:
        logger.info("Mart exists, skipping: %s", mart_path)
        return pl.read_parquet(mart_path)

    acs = extract_acs(settings, metro, granularity="block_group")
    acs = acs.filter(pl.col("state_fips").is_in(metro.state_fips_set))
    acs = acs.filter(pl.col("tract_fips").is_not_null())

    base = _build_acs_base(acs)

    epa_path = find_parquet(staging / "epa_sld")
    if epa_path and epa_path.exists():
        epa = pl.read_parquet(epa_path)
        base = _join_epa_sld(base, epa)
    else:
        logger.warning("EPA SLD missing — walkability columns will be null")

    umr_path = staging / "umr" / f"umr_{metro.metro_id}.parquet"
    if umr_path.exists():
        umr = pl.read_parquet(umr_path)
        base = infer_congestion(base, umr)
    else:
        logger.warning("UMR missing — congestion columns will be null")
        base = base.with_columns(
            pl.lit(None).cast(pl.Float64).alias("total_delay_hours"),
            pl.lit(None).cast(pl.Float64).alias("total_congestion_cost"),
            pl.lit(None).cast(pl.Float64).alias("delay_per_capita"),
            pl.lit(None).cast(pl.Float64).alias("congestion_cost_per_capita"),
        )

    ntd_path = find_parquet(staging / "ntd")
    if ntd_path:
        ntd = pl.read_parquet(ntd_path)
        base = infer_ridership(base, ntd)
    else:
        logger.warning("NTD missing — ridership columns will be null")
        base = base.with_columns(
            pl.lit(None).cast(pl.Int64).alias("total_annual_ridership"),
            pl.lit(None).cast(pl.Float64).alias("ridership_per_capita"),
        )

    geojson_path = settings.web_data_dir(metro.metro_id) / "block_groups.geojson"
    boundaries = load_boundaries(geojson_path) if geojson_path.exists() else None

    fars_path = find_parquet(staging / "fars")
    if fars_path and fars_path.exists() and boundaries:
        fars = pl.read_parquet(fars_path)
        fars_agg = _aggregate_fars_to_block_groups(fars, boundaries)
        base = base.join(fars_agg, on="geoid_12", how="left")
    else:
        logger.warning("FARS or block group GeoJSON missing — crash columns will be null")

    parks_path = find_parquet(staging / "osm_parks")
    if parks_path and parks_path.exists() and boundaries:
        parks = pl.read_parquet(parks_path)
        centroids = compute_centroids(boundaries)
        proximity = compute_amenity_proximity(centroids, parks)
        base = base.join(
            proximity.select("area_id", "park_count_nearby", "total_park_area_sqm"),
            left_on="geoid_12",
            right_on="area_id",
            how="left",
        )
        base = base.with_columns(
            pl.col("park_count_nearby").fill_null(0),
            pl.col("total_park_area_sqm").fill_null(0.0),
        )
        logger.info("Park proximity: joined %d block groups", len(proximity))
    else:
        logger.warning("OSM parks or block group GeoJSON missing — park columns will be null")

    # Block groups with no FARS crashes should be 0, not null
    safety_cols = ["total_fatalities", "total_crashes", "pedestrian_involved_crashes", "drunk_driver_crashes"]
    base = base.with_columns([pl.col(c).fill_null(0) for c in safety_cols if c in base.columns])

    # Per-capita crash rates (mirrors county_mart calculations)
    if "total_crashes" in base.columns:
        base = base.with_columns(
            pl.when(pl.col("total_population") > 0)
            .then(pl.col("total_fatalities").cast(pl.Float64) / pl.col("total_population").cast(pl.Float64))
            .otherwise(None)
            .alias("fatalities_per_capita"),
            pl.when(pl.col("total_population") > 0)
            .then(pl.col("total_crashes").cast(pl.Float64) / pl.col("total_population").cast(pl.Float64))
            .otherwise(None)
            .alias("crashes_per_capita"),
        )

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
        "park_count_nearby": pl.Int64,
        "total_park_area_sqm": pl.Float64,
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
    base = base.with_columns(pl.lit(metro.metro_id).alias("metro_id"))

    mart_path.parent.mkdir(parents=True, exist_ok=True)
    base.write_parquet(mart_path)
    logger.info(
        "Wrote block group mart: %d rows to %s", len(base), mart_path
    )

    json_path = settings.web_data_dir(metro.metro_id) / "block_group_summary.json"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    records = sanitize_records(base.to_dicts())
    json_path.write_text(json.dumps(records, default=str))
    logger.info("Wrote block group JSON: %d rows to %s", len(records), json_path)

    return base
