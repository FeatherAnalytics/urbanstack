import logging

import polars as pl

logger = logging.getLogger(__name__)


def infer_ridership(base: pl.DataFrame, ntd: pl.DataFrame) -> pl.DataFrame:
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
        (pl.col("pct_transit") * pl.col("total_commuters")).alias("_transit_commuters"),
    )
    metro_transit_commuters = base.select(pl.col("_transit_commuters").sum()).item()

    if not metro_transit_commuters or metro_transit_commuters == 0:
        return base.drop("_transit_commuters").with_columns(
            pl.lit(None).cast(pl.Int64).alias("total_annual_ridership"),
            pl.lit(None).cast(pl.Float64).alias("ridership_per_capita"),
        )

    base = base.with_columns(
        (
            pl.lit(metro_total_ridership)
            * (pl.col("_transit_commuters") / pl.lit(metro_transit_commuters))
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
    return base.drop("_transit_commuters")


def infer_congestion(base: pl.DataFrame, umr: pl.DataFrame) -> pl.DataFrame:
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


def sanitize_records(records: list[dict]) -> list[dict]:
    for r in records:
        for k, v in r.items():
            if isinstance(v, float) and (v != v or v == float("inf") or v == float("-inf")):
                r[k] = None
    return records
