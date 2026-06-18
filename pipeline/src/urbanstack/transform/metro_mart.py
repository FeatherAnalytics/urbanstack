import json
import logging
from pathlib import Path

import polars as pl

from urbanstack.config import Settings
from urbanstack.transform.county_mart import build_county_mart

logger = logging.getLogger(__name__)

METRO_FIPS = "48DFW"
METRO_NAME = "Dallas-Fort Worth-Arlington MSA"


def build_metro_mart(settings: Settings, *, force: bool = False) -> pl.DataFrame:
    mart_path = settings.marts_dir / "metro_summary.parquet"

    if mart_path.exists() and not force:
        logger.info("Mart exists, skipping: %s", mart_path)
        return pl.read_parquet(mart_path)

    county = build_county_mart(settings)

    sum_cols = ["population", "total_commuters", "vehicles_available"]
    sum_exprs = [
        pl.col(c).sum().alias(c) for c in sum_cols if c in county.columns
    ]

    pop_weighted_cols = [
        "per_capita_income",
        "median_household_income",
        "median_rent",
        "median_home_value",
    ]
    pop_wt_exprs = []
    for c in pop_weighted_cols:
        if c in county.columns:
            pop_wt_exprs.append(
                (pl.col(c).cast(pl.Float64) * pl.col("population").cast(pl.Float64))
                .sum()
                .alias(f"_weighted_{c}")
            )

    avg_cols = [
        "avg_walkability",
        "avg_pop_density",
        "avg_job_density",
        "avg_intersection_density",
        "avg_transit_frequency",
        "pct_zero_car_hh",
    ]
    avg_exprs = [
        pl.col(c).mean().alias(c) for c in avg_cols if c in county.columns
    ]

    commute_sum_cols = [
        "pct_drove_alone",
        "pct_transit",
        "pct_walked",
        "pct_biked",
        "pct_wfh",
    ]

    total_pop_expr = [pl.col("population").sum().alias("_total_pop")]

    all_exprs = sum_exprs + pop_wt_exprs + avg_exprs + total_pop_expr

    agg = county.select(all_exprs)
    row = agg.to_dicts()[0]

    total_pop = row["_total_pop"]
    result: dict[str, object] = {
        "county_fips": METRO_FIPS,
        "county_name": METRO_NAME,
    }

    for c in sum_cols:
        if c in county.columns:
            result[c] = row[c]

    for c in pop_weighted_cols:
        key = f"_weighted_{c}"
        if key in row and total_pop and total_pop > 0:
            result[c] = row[key] / total_pop
        else:
            result[c] = None

    for c in avg_cols:
        if c in county.columns:
            result[c] = row[c]

    if "total_commuters" in row and row["total_commuters"] and row["total_commuters"] > 0:
        total_comm = row["total_commuters"]
        for pct_col in commute_sum_cols:
            if pct_col in county.columns:
                raw_col = f"commute_{pct_col.removeprefix('pct_')}"
                if raw_col in county.columns:
                    raw_sum = county.select(pl.col(raw_col).sum()).item()
                    result[pct_col] = raw_sum / total_comm if total_comm > 0 else None
                else:
                    weighted = county.select(
                        (pl.col(pct_col) * pl.col("total_commuters")).sum()
                    ).item()
                    result[pct_col] = weighted / total_comm if total_comm > 0 else None
    else:
        for pct_col in commute_sum_cols:
            result[pct_col] = None

    if "federal_obligation" in county.columns:
        result["federal_obligation"] = county.select(
            pl.col("federal_obligation").sum()
        ).item()
        if total_pop and total_pop > 0 and result["federal_obligation"]:
            result["federal_per_capita"] = result["federal_obligation"] / total_pop
        else:
            result["federal_per_capita"] = None
    else:
        result["federal_obligation"] = None
        result["federal_per_capita"] = None

    if "land_area_sqmi" in county.columns:
        total_land = county.select(pl.col("land_area_sqmi").sum()).item()
        if total_pop and total_land and total_land > 0:
            result["pop_density_sqmi"] = total_pop / total_land
        else:
            result["pop_density_sqmi"] = None
    else:
        result["pop_density_sqmi"] = None

    safety_cols = [
        "total_fatalities",
        "total_crashes",
        "pedestrian_involved_crashes",
        "drunk_driver_crashes",
    ]
    for c in safety_cols:
        if c in county.columns:
            result[c] = county.select(pl.col(c).sum()).item()
        else:
            result[c] = None

    congestion_cols = [
        "travel_time_index",
        "planning_time_index",
        "annual_delay_hours",
        "congestion_cost",
    ]
    for c in congestion_cols:
        if c in county.columns:
            result[c] = county.select(pl.col(c).mean()).item()
        else:
            result[c] = None

    area_cols = ["land_area_sqm", "water_area_sqm", "land_area_sqmi", "latitude", "longitude"]
    for c in area_cols:
        if c in county.columns:
            if c in ("latitude", "longitude"):
                result[c] = county.select(pl.col(c).mean()).item()
            else:
                result[c] = county.select(pl.col(c).sum()).item()
        else:
            result[c] = None

    metro_df = pl.DataFrame([result])

    settings.marts_dir.mkdir(parents=True, exist_ok=True)
    metro_df.write_parquet(mart_path)
    logger.info("Wrote metro mart: %s", mart_path)

    json_path = (
        Path(settings.data_dir).resolve().parent.parent
        / "web" / "public" / "data" / "metro_summary.json"
    )
    json_path.parent.mkdir(parents=True, exist_ok=True)
    records = metro_df.to_dicts()
    json_path.write_text(json.dumps(records, default=str))
    logger.info("Wrote metro JSON: %s", json_path)

    return metro_df
