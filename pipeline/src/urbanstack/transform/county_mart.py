import json
import logging
from pathlib import Path

import polars as pl

from urbanstack.config import Settings
from urbanstack.geography import DFW_STATE_FIPS
from urbanstack.transform.derived import apply_derived_metrics
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


def _aggregate_fhwa(fhwa: pl.DataFrame, stations: pl.DataFrame) -> pl.DataFrame:
    """Join volumes to station-county mapping and compute avg daily traffic per county."""
    joined = fhwa.join(
        stations.select("station_id", "county_fips"),
        on="station_id",
        how="inner",
    )

    if joined.is_empty():
        fhwa_norm = fhwa.with_columns(
            pl.col("station_id").str.lstrip_chars("0").alias("_sid"),
        )
        stations_norm = stations.with_columns(
            pl.col("station_id").str.lstrip_chars("0").alias("_sid"),
        )
        joined = fhwa_norm.join(
            stations_norm.select("_sid", "county_fips"),
            on="_sid",
            how="inner",
        )

    if joined.is_empty():
        logger.warning("FHWA: no stations matched after join")
        return pl.DataFrame({"county_fips": [], "avg_daily_traffic": []}).cast(
            {"county_fips": pl.Utf8, "avg_daily_traffic": pl.Float64}
        )

    return joined.group_by("county_fips").agg(
        pl.col("daily_volume").mean().alias("avg_daily_traffic"),
    )


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
        (pl.col("pct_transit") * pl.col("total_commuters")).alias("_county_transit_commuters"),
    )
    metro_transit_commuters = base.select(pl.col("_county_transit_commuters").sum()).item()

    if not metro_transit_commuters or metro_transit_commuters == 0:
        return base.drop("_county_transit_commuters").with_columns(
            pl.lit(None).cast(pl.Int64).alias("total_annual_ridership"),
            pl.lit(None).cast(pl.Float64).alias("ridership_per_capita"),
        )

    base = base.with_columns(
        (
            pl.lit(metro_total_ridership)
            * (pl.col("_county_transit_commuters") / pl.lit(metro_transit_commuters))
        )
        .cast(pl.Int64)
        .alias("total_annual_ridership"),
    )
    base = base.with_columns(
        (pl.col("total_annual_ridership").cast(pl.Float64) / pl.col("total_population").cast(pl.Float64))
        .alias("ridership_per_capita"),
    )
    return base.drop("_county_transit_commuters")


def _infer_congestion(base: pl.DataFrame, umr: pl.DataFrame) -> pl.DataFrame:
    latest = umr.sort("year", descending=True).head(1).to_dicts()[0]
    delay_per = latest.get("annual_delay_per_commuter")
    cost_per = latest.get("congestion_cost_per_commuter")

    base = base.with_columns(
        (pl.col("pct_drove_alone") * pl.col("total_commuters")).alias("_auto_commuters"),
    )
    base = base.with_columns(
        (pl.lit(delay_per) * pl.col("_auto_commuters")).cast(pl.Float64).alias("total_delay_hours"),
        (pl.lit(cost_per) * pl.col("_auto_commuters")).cast(pl.Float64).alias("total_congestion_cost"),
    )
    base = base.with_columns(
        (pl.col("total_delay_hours") / pl.col("total_population").cast(pl.Float64)).alias("delay_per_capita"),
        (pl.col("total_congestion_cost") / pl.col("total_population").cast(pl.Float64)).alias("congestion_cost_per_capita"),
    )
    return base.drop("_auto_commuters")


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
        base = base.with_columns(
            (pl.col("total_fatalities").cast(pl.Float64) / pl.col("total_population").cast(pl.Float64)).alias("fatalities_per_capita"),
            (pl.col("total_crashes").cast(pl.Float64) / pl.col("total_population").cast(pl.Float64)).alias("crashes_per_capita"),
        )
    else:
        logger.warning("FARS missing — crash columns will be null")

    umr_path = settings.staging_dir / "umr" / "umr_dfw.parquet"
    umr = _read_staging(umr_path, "umr")
    if umr is not None:
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
    ntd = _read_staging(ntd_path, "ntd") if ntd_path else None
    if ntd is not None:
        base = _infer_ridership(base, ntd)
    else:
        logger.warning("NTD missing — ridership columns will be null")

    usa_dir = settings.staging_dir / "usaspending"
    usa_path = find_parquet(usa_dir)
    usa = _read_staging(usa_path, "usaspending") if usa_path else None
    if usa is not None:
        usa_sel = _select_usaspending(usa)
        base = base.join(usa_sel, on="county_fips", how="left")
    else:
        logger.warning("USAspending missing — federal spending columns will be null")

    fhwa_path = find_parquet(settings.staging_dir / "fhwa")
    fhwa = _read_staging(fhwa_path, "fhwa") if fhwa_path else None
    stations_path = find_parquet(settings.staging_dir / "tmas_stations")
    stations = _read_staging(stations_path, "tmas_stations") if stations_path else None
    if fhwa is not None and stations is not None:
        fhwa_agg = _aggregate_fhwa(fhwa, stations)
        base = base.join(fhwa_agg, on="county_fips", how="left")
    else:
        logger.warning("FHWA or station mapping missing — traffic volume columns will be null")

    rename_map: dict[str, str] = {
        "total_population": "population",
        "pop_density": "pop_density_sqmi",
    }
    # Only rename columns that exist (graceful when sources missing)
    rename_map = {k: v for k, v in rename_map.items() if k in base.columns}
    base = base.rename(rename_map)

    base = apply_derived_metrics(base)

    settings.marts_dir.mkdir(parents=True, exist_ok=True)
    base.write_parquet(mart_path)
    logger.info("Wrote county mart: %d rows to %s", len(base), mart_path)

    json_path = (
        Path(settings.data_dir).resolve().parent.parent
        / "web" / "public" / "data" / "county_summary.json"
    )
    json_path.parent.mkdir(parents=True, exist_ok=True)
    records = _sanitize_records(base.to_dicts())
    json_path.write_text(json.dumps(records, indent=2, default=str))
    logger.info("Wrote county JSON: %d rows to %s", len(records), json_path)

    return base


def _aggregate_fars_year(fars: pl.DataFrame, year: int) -> pl.DataFrame:
    df = fars.filter(pl.col("year") == year).with_columns(
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


def _ridership_for_year(
    ntd: pl.DataFrame,
    year: int,
    county_transit_shares: pl.DataFrame,
) -> pl.DataFrame | None:
    year_data = ntd.filter(pl.col("year") == year)
    n_months = year_data.select(pl.col("month").n_unique()).item()
    if n_months < 12:
        return None

    metro_total = year_data.select(pl.col("unlinked_passenger_trips").sum()).item()
    metro_commuters = county_transit_shares.select(pl.col("county_transit_commuters").sum()).item()

    if not metro_commuters or metro_commuters == 0:
        return county_transit_shares.select("county_fips").with_columns(
            pl.lit(None).cast(pl.Int64).alias("total_annual_ridership"),
        )

    return county_transit_shares.with_columns(
        (
            pl.lit(metro_total)
            * (pl.col("county_transit_commuters") / pl.lit(metro_commuters))
        )
        .cast(pl.Int64)
        .alias("total_annual_ridership"),
    ).select("county_fips", "total_annual_ridership")


def _sanitize_records(records: list[dict]) -> list[dict]:
    for r in records:
        for k, v in r.items():
            if isinstance(v, float) and (v != v):
                r[k] = None
    return records


def build_year_overlays(settings: Settings) -> None:
    web_dir = (
        Path(settings.data_dir).resolve().parent.parent
        / "web" / "public" / "data" / "overlays"
    )
    web_dir.mkdir(parents=True, exist_ok=True)

    acs_path = find_parquet(settings.staging_dir / "acs")
    if acs_path is None:
        logger.warning("ACS missing — cannot build year overlays (need commute shares)")
        return

    acs = pl.read_parquet(acs_path).filter(pl.col("state_fips") == DFW_STATE_FIPS)
    if "tract_fips" in acs.columns:
        acs = acs.filter(pl.col("tract_fips").is_null())
    base = _build_acs_base(acs)

    county_transit_shares = base.select(
        "county_fips",
        (pl.col("pct_transit") * pl.col("total_commuters")).alias("county_transit_commuters"),
    )

    fars_files = sorted((settings.staging_dir / "fars").glob("*.parquet")) if (settings.staging_dir / "fars").exists() else []
    fars: pl.DataFrame | None = None
    if fars_files:
        fars = pl.concat([pl.read_parquet(f) for f in fars_files]).unique()

    ntd_path = find_parquet(settings.staging_dir / "ntd")
    ntd: pl.DataFrame | None = _read_staging(ntd_path, "ntd") if ntd_path else None

    if fars is None and ntd is None:
        logger.warning("No FARS or NTD data — skipping year overlays")
        return

    fars_years: set[int] = set(fars["year"].unique().to_list()) if fars is not None else set()
    ntd_years: set[int] = set()
    if ntd is not None:
        full_years = (
            ntd.group_by("year")
            .agg(pl.col("month").n_unique().alias("n_months"))
            .filter(pl.col("n_months") >= 12)
        )
        ntd_years = set(full_years["year"].to_list())

    all_years = sorted(fars_years | ntd_years)
    written_years: list[int] = []

    for year in all_years:
        overlay: pl.DataFrame | None = None

        if year in fars_years and fars is not None:
            overlay = _aggregate_fars_year(fars, year)

        if year in ntd_years and ntd is not None:
            ridership = _ridership_for_year(ntd, year, county_transit_shares)
            if ridership is not None:
                overlay = overlay.join(ridership, on="county_fips", how="outer_coalesce") if overlay is not None else ridership

        if overlay is not None and not overlay.is_empty():
            records = _sanitize_records(overlay.to_dicts())
            out_path = web_dir / f"county_{year}.json"
            out_path.write_text(json.dumps(records, indent=2, default=str))
            written_years.append(year)

    index = {"years": written_years}
    (web_dir / "index.json").write_text(json.dumps(index, indent=2))
    logger.info("Wrote %d year overlays to %s", len(written_years), web_dir)
