import logging
from dataclasses import dataclass, field
from typing import Callable

import polars as pl

logger = logging.getLogger(__name__)


MIN_POP_FOR_RATES = 100


@dataclass(frozen=True)
class DerivedMetric:
    name: str
    dtype: type
    requires: list[str]
    compute: Callable[[pl.DataFrame], pl.Expr]
    exclude_granularities: list[str] = field(default_factory=list)
    min_population: int = 0


DERIVED_METRICS: list[DerivedMetric] = [
    DerivedMetric(
        name="crash_rate_per_1k_commuters",
        dtype=pl.Float64,
        requires=["total_fatalities", "total_commuters"],
        compute=lambda _: (
            pl.col("total_fatalities").cast(pl.Float64)
            / pl.col("total_commuters").cast(pl.Float64)
            * 1000
        ),
        min_population=MIN_POP_FOR_RATES,
    ),
    DerivedMetric(
        name="ped_fatality_rate_per_100k",
        dtype=pl.Float64,
        requires=["pedestrian_involved_crashes", "population"],
        compute=lambda _: (
            pl.col("pedestrian_involved_crashes").cast(pl.Float64)
            / pl.col("population").cast(pl.Float64)
            * 100_000
        ),
        min_population=MIN_POP_FOR_RATES,
    ),
    DerivedMetric(
        name="congestion_cost_pct_income",
        dtype=pl.Float64,
        requires=["congestion_cost_per_capita", "per_capita_income"],
        compute=lambda _: (
            pl.col("congestion_cost_per_capita").cast(pl.Float64)
            / pl.col("per_capita_income").cast(pl.Float64)
        ),
    ),
    DerivedMetric(
        name="delay_pct_work_hours",
        dtype=pl.Float64,
        requires=["total_delay_hours", "total_commuters"],
        compute=lambda _: (
            pl.col("total_delay_hours").cast(pl.Float64)
            / pl.col("total_commuters").cast(pl.Float64)
            / 2080.0
        ),
        exclude_granularities=["block_group"],
    ),
    DerivedMetric(
        name="federal_per_crash",
        dtype=pl.Float64,
        requires=["federal_obligation", "total_crashes"],
        compute=lambda _: (
            pl.col("federal_obligation").cast(pl.Float64)
            / pl.col("total_crashes").cast(pl.Float64)
        ),
    ),
    DerivedMetric(
        name="vehicle_dependency",
        dtype=pl.Float64,
        requires=["pct_zero_car_hh", "pct_drove_alone"],
        compute=lambda _: (
            (1.0 - pl.col("pct_zero_car_hh").cast(pl.Float64))
            * pl.col("pct_drove_alone").cast(pl.Float64)
        ),
    ),
    DerivedMetric(
        name="drunk_driver_crashes_per_capita",
        dtype=pl.Float64,
        requires=["drunk_driver_crashes", "population"],
        compute=lambda _: (
            pl.col("drunk_driver_crashes").cast(pl.Float64)
            / pl.col("population").cast(pl.Float64)
            * 100_000
        ),
        min_population=MIN_POP_FOR_RATES,
    ),
    DerivedMetric(
        name="pedestrian_crashes_per_capita",
        dtype=pl.Float64,
        requires=["pedestrian_involved_crashes", "population"],
        compute=lambda _: (
            pl.col("pedestrian_involved_crashes").cast(pl.Float64)
            / pl.col("population").cast(pl.Float64)
            * 100_000
        ),
        min_population=MIN_POP_FOR_RATES,
    ),
]


def apply_derived_metrics(df: pl.DataFrame, *, granularity: str = "") -> pl.DataFrame:
    """Apply all derived metrics whose required columns exist in the dataframe.

    Metrics with missing requirements get null columns.
    Metrics excluded at the given granularity are skipped entirely.
    """
    for metric in DERIVED_METRICS:
        if granularity and granularity in metric.exclude_granularities:
            logger.debug("Skipping %s — excluded at %s", metric.name, granularity)
            continue
        if all(col in df.columns for col in metric.requires):
            df = df.with_columns(metric.compute(df).alias(metric.name))
            if metric.min_population > 0 and "population" in df.columns:
                df = df.with_columns(
                    pl.when(pl.col("population") >= metric.min_population)
                    .then(pl.col(metric.name))
                    .otherwise(None)
                    .alias(metric.name)
                )
        else:
            missing = [c for c in metric.requires if c not in df.columns]
            logger.debug(
                "Skipping %s — missing columns: %s", metric.name, missing
            )
            df = df.with_columns(
                pl.lit(None).cast(metric.dtype).alias(metric.name)
            )
    return df
