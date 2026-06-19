import json
import logging

import polars as pl

from urbanstack.config import Settings
from urbanstack.metro import MetroConfig
from urbanstack.transform._shared import sanitize_records
from urbanstack.transform.county_mart import build_county_mart
from urbanstack.transform.derived import apply_derived_metrics
from urbanstack.utils import find_parquet

logger = logging.getLogger(__name__)


def build_metro_mart(settings: Settings, metro: MetroConfig, *, force: bool = False) -> pl.DataFrame:
    staging = settings.metro_staging_dir(metro.metro_id)
    mart_path = settings.metro_marts_dir(metro.metro_id) / "metro_summary.parquet"

    if mart_path.exists() and not force:
        logger.info("Mart exists, skipping: %s", mart_path)
        return pl.read_parquet(mart_path)

    county = build_county_mart(settings, metro)

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
        "county_fips": metro.metro_fips,
        "county_name": metro.metro_name,
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

    if result.get("total_fatalities") and total_pop and total_pop > 0:
        result["fatalities_per_capita"] = result["total_fatalities"] / total_pop
    else:
        result["fatalities_per_capita"] = None
    if result.get("total_crashes") and total_pop and total_pop > 0:
        result["crashes_per_capita"] = result["total_crashes"] / total_pop
    else:
        result["crashes_per_capita"] = None

    umr_path = staging / "umr" / f"umr_{metro.metro_id}.parquet"
    if umr_path.exists():
        umr = pl.read_parquet(umr_path)
        latest = umr.sort("year", descending=True).head(1).to_dicts()[0]
        result["travel_time_index"] = latest.get("travel_time_index")
        result["planning_time_index"] = latest.get("planning_time_index")
        result["annual_delay_hours"] = latest.get("annual_delay_per_commuter")
        result["congestion_cost"] = latest.get("congestion_cost_per_commuter")
    else:
        result["travel_time_index"] = None
        result["planning_time_index"] = None
        result["annual_delay_hours"] = None
        result["congestion_cost"] = None

    if "total_delay_hours" in county.columns:
        result["total_delay_hours"] = county.select(pl.col("total_delay_hours").sum()).item()
    else:
        result["total_delay_hours"] = None
    if "total_congestion_cost" in county.columns:
        result["total_congestion_cost"] = county.select(pl.col("total_congestion_cost").sum()).item()
    else:
        result["total_congestion_cost"] = None

    if result.get("total_delay_hours") and total_pop and total_pop > 0:
        result["delay_per_capita"] = result["total_delay_hours"] / total_pop
    else:
        result["delay_per_capita"] = None
    if result.get("total_congestion_cost") and total_pop and total_pop > 0:
        result["congestion_cost_per_capita"] = result["total_congestion_cost"] / total_pop
    else:
        result["congestion_cost_per_capita"] = None

    if "total_annual_ridership" in county.columns:
        result["total_annual_ridership"] = county.select(pl.col("total_annual_ridership").sum()).item()
    else:
        result["total_annual_ridership"] = None

    if result.get("total_annual_ridership") and total_pop and total_pop > 0:
        result["ridership_per_capita"] = result["total_annual_ridership"] / total_pop
    else:
        result["ridership_per_capita"] = None

    ntd_path = find_parquet(staging / "ntd")
    if ntd_path:
        ntd = pl.read_parquet(ntd_path)
        full_years = (
            ntd.group_by("year")
            .agg(pl.col("month").n_unique().alias("n_months"))
            .filter(pl.col("n_months") >= 12)
            .sort("year", descending=True)
        )
        if not full_years.is_empty():
            latest_year = full_years["year"][0]
            year_data = ntd.filter(pl.col("year") == latest_year)
            result["transit_revenue_miles"] = year_data.select(
                pl.col("vehicle_revenue_miles").sum()
            ).item()
        else:
            result["transit_revenue_miles"] = None
    else:
        result["transit_revenue_miles"] = None

    if "avg_daily_traffic" in county.columns:
        result["avg_daily_traffic"] = county.select(
            pl.col("avg_daily_traffic").mean()
        ).item()
    else:
        result["avg_daily_traffic"] = None

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
    metro_df = apply_derived_metrics(metro_df)
    metro_df = metro_df.with_columns(pl.lit(metro.metro_id).alias("metro_id"))

    mart_path.parent.mkdir(parents=True, exist_ok=True)
    metro_df.write_parquet(mart_path)
    logger.info("Wrote metro mart: %s", mart_path)

    json_path = settings.web_data_dir(metro.metro_id) / "metro_summary.json"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    records = sanitize_records(metro_df.to_dicts())
    json_path.write_text(json.dumps(records, default=str))
    logger.info("Wrote metro JSON: %s", json_path)

    return metro_df
