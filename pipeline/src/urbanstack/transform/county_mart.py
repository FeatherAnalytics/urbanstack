import json
import logging
from pathlib import Path

import polars as pl

from urbanstack.config import Settings
from urbanstack.geography import DFW_STATE_FIPS
from urbanstack.utils import find_parquet

logger = logging.getLogger(__name__)


def _read_staging(path: Path, source_name: str) -> pl.DataFrame | None:
    if not path.exists():
        logger.warning("Staging file missing, skipping %s: %s", source_name, path)
        return None
    return pl.read_parquet(path)


def _build_acs_base(acs: pl.DataFrame) -> pl.DataFrame:
    df = acs.with_columns(
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
        pl.sum_horizontal([pl.col(c).fill_null(0) for c in commute_cols]).alias("total_commuters"),
    )

    for col in commute_cols:
        pct_name = f"pct_{col.removeprefix('commute_')}"
        df = df.with_columns(
            pl.when(pl.col("total_commuters") > 0)
            .then(pl.col(col).cast(pl.Float64) / pl.col("total_commuters").cast(pl.Float64))
            .otherwise(None)
            .alias(pct_name),
        )

    keep = [
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

    return df.select(keep).rename({"county_fips_5": "county_fips", "name": "county_name"})


def _aggregate_epa_sld(epa: pl.DataFrame) -> pl.DataFrame:
    df = epa.with_columns(
        (pl.col("state_fips") + pl.col("county_fips")).alias("county_fips_5"),
    )

    agg_cols = {
        "nat_walk_ind": "avg_walkability",
        "d1b": "avg_pop_density",
        "d1c": "avg_job_density",
        "d3b": "avg_intersection_density",
        "d4d": "avg_transit_frequency",
        "pct_ao0": "pct_zero_car_hh",
    }

    agg_exprs = [pl.col(src).mean().alias(dst) for src, dst in agg_cols.items()]

    return df.group_by("county_fips_5").agg(agg_exprs).rename({"county_fips_5": "county_fips"})


def _aggregate_fars(fars: pl.DataFrame) -> pl.DataFrame:
    df = fars.with_columns(
        (pl.col("state_fips") + pl.col("county_fips")).alias("county_fips_5"),
    )

    return (
        df.group_by("county_fips_5")
        .agg(
            pl.col("fatalities").sum().alias("total_fatalities"),
            pl.len().alias("total_crashes"),
            pl.col("pedestrians")
            .filter(pl.col("pedestrians") > 0)
            .sum()
            .alias("pedestrian_involved_crashes"),
            pl.col("drunk_drivers")
            .filter(pl.col("drunk_drivers") > 0)
            .sum()
            .alias("drunk_driver_crashes"),
        )
        .rename({"county_fips_5": "county_fips"})
    )


def _join_umr(base: pl.DataFrame, umr: pl.DataFrame) -> pl.DataFrame:
    """Add metro-level UMR congestion metrics as constant columns.

    UMR data is metro-level (same values for all DFW counties), so we
    take the latest year's row and broadcast to every county.
    """
    latest = umr.sort("year", descending=True).head(1).to_dicts()[0]
    return base.with_columns(
        pl.lit(latest.get("travel_time_index")).cast(pl.Float64).alias("travel_time_index"),
        pl.lit(latest.get("planning_time_index")).cast(pl.Float64).alias("planning_time_index"),
        pl.lit(latest.get("annual_delay_per_commuter")).cast(pl.Float64).alias("annual_delay_hours"),
        pl.lit(latest.get("congestion_cost_per_commuter")).cast(pl.Float64).alias("congestion_cost"),
    )


def _select_usaspending(usa: pl.DataFrame) -> pl.DataFrame:
    return usa.select(
        pl.col("county_fips"),
        pl.col("total_obligation").alias("federal_obligation"),
        pl.col("per_capita").alias("federal_per_capita"),
    )


def _join_gazetteer(base: pl.DataFrame, gaz: pl.DataFrame) -> pl.DataFrame:
    gaz_cols = gaz.select(
        pl.col("county_fips"),
        pl.col("land_area_sqm"),
        pl.col("water_area_sqm"),
        (pl.col("land_area_sqm").cast(pl.Float64) / 2_589_988.0).alias("land_area_sqmi"),
        pl.col("latitude"),
        pl.col("longitude"),
    )
    base = base.join(gaz_cols, on="county_fips", how="left")

    return base.with_columns(
        (pl.col("total_population").cast(pl.Float64) / pl.col("land_area_sqmi")).alias(
            "pop_density"
        ),
    )


def build_county_mart(settings: Settings, *, force: bool = False) -> pl.DataFrame:
    mart_path = settings.marts_dir / "county_summary.parquet"

    if mart_path.exists() and not force:
        logger.info("Mart exists, skipping: %s", mart_path)
        return pl.read_parquet(mart_path)

    acs_path = settings.staging_dir / "acs" / "acs_county_2023.parquet"
    if not acs_path.exists():
        acs_path = find_parquet(settings.staging_dir / "acs")
    if acs_path is None:
        raise FileNotFoundError(
            f"ACS staging parquet required but not found in {settings.staging_dir / 'acs'}"
        )

    acs = pl.read_parquet(acs_path)
    acs = acs.filter(pl.col("state_fips") == DFW_STATE_FIPS)
    if "tract_fips" in acs.columns:
        acs = acs.filter(pl.col("tract_fips").is_null())

    base = _build_acs_base(acs)

    gaz_path = find_parquet(settings.staging_dir / "gazetteer")
    gaz = _read_staging(gaz_path, "gazetteer") if gaz_path else None
    if gaz is not None:
        base = _join_gazetteer(base, gaz)
    else:
        logger.warning("Gazetteer missing — pop_density and area columns will be null")
        base = base.with_columns(
            pl.lit(None).cast(pl.Int64).alias("land_area_sqm"),
            pl.lit(None).cast(pl.Int64).alias("water_area_sqm"),
            pl.lit(None).cast(pl.Float64).alias("land_area_sqmi"),
            pl.lit(None).cast(pl.Float64).alias("latitude"),
            pl.lit(None).cast(pl.Float64).alias("longitude"),
            pl.lit(None).cast(pl.Float64).alias("pop_density"),
        )

    epa_path = find_parquet(settings.staging_dir / "epa_sld")
    epa = _read_staging(epa_path, "epa_sld") if epa_path else None
    if epa is not None:
        epa_agg = _aggregate_epa_sld(epa)
        base = base.join(epa_agg, on="county_fips", how="left")
    else:
        logger.warning("EPA SLD missing — walkability columns will be null")

    fars_path = find_parquet(settings.staging_dir / "fars")
    fars = _read_staging(fars_path, "fars") if fars_path else None
    if fars is not None:
        fars_agg = _aggregate_fars(fars)
        base = base.join(fars_agg, on="county_fips", how="left")
    else:
        logger.warning("FARS missing — crash columns will be null")

    umr_path = settings.staging_dir / "umr" / "umr_dfw.parquet"
    umr = _read_staging(umr_path, "umr")
    if umr is not None:
        base = _join_umr(base, umr)
    else:
        logger.warning("UMR missing — congestion columns will be null")

    usa_dir = settings.staging_dir / "usaspending"
    usa_path = find_parquet(usa_dir)
    usa = _read_staging(usa_path, "usaspending") if usa_path else None
    if usa is not None:
        usa_sel = _select_usaspending(usa)
        base = base.join(usa_sel, on="county_fips", how="left")
    else:
        logger.warning("USAspending missing — federal spending columns will be null")

    rename_map: dict[str, str] = {
        "total_population": "population",
        "pop_density": "pop_density_sqmi",
    }
    # Only rename columns that exist (graceful when sources missing)
    rename_map = {k: v for k, v in rename_map.items() if k in base.columns}
    base = base.rename(rename_map)

    settings.marts_dir.mkdir(parents=True, exist_ok=True)
    base.write_parquet(mart_path)
    logger.info("Wrote county mart: %d rows to %s", len(base), mart_path)

    json_path = (
        Path(settings.data_dir).resolve().parent.parent
        / "web" / "public" / "data" / "county_summary.json"
    )
    json_path.parent.mkdir(parents=True, exist_ok=True)
    records = base.to_dicts()
    for r in records:
        for k, v in r.items():
            if isinstance(v, float) and (v != v):
                r[k] = None
    json_path.write_text(json.dumps(records, indent=2, default=str))
    logger.info("Wrote county JSON: %d rows to %s", len(records), json_path)

    return base
