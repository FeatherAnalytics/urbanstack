import logging
import time
from dataclasses import dataclass
from pathlib import Path

import polars as pl
import requests

from urbanstack.config import Settings
from urbanstack.metro import MetroConfig

logger = logging.getLogger(__name__)

CATALOG_URL = "https://files.mobilitydatabase.org/feeds_v2.csv"
CATALOG_MAX_AGE_SECONDS = 86400


@dataclass(frozen=True)
class DiscoveredFeed:
    mdb_id: str
    provider: str
    download_url: str
    stable_url: str
    municipality: str
    subdivision: str


def _download_catalog(settings: Settings, *, force: bool = False) -> Path:
    catalog_dir = settings.raw_dir / "catalog"
    catalog_dir.mkdir(parents=True, exist_ok=True)
    csv_path = catalog_dir / "feeds_v2.csv"

    if csv_path.exists() and not force:
        age = time.time() - csv_path.stat().st_mtime
        if age < CATALOG_MAX_AGE_SECONDS:
            logger.info("Catalog cache fresh (%.0fh old), skipping download", age / 3600)
            return csv_path

    headers = {"User-Agent": "UrbanStack/1.0 (transit data pipeline)"}
    resp = requests.get(CATALOG_URL, headers=headers, timeout=60)
    resp.raise_for_status()
    csv_path.write_bytes(resp.content)
    logger.info("Downloaded Mobility Database catalog to %s", csv_path)
    return csv_path


def discover_feeds(
    settings: Settings,
    metro: MetroConfig,
    *,
    force: bool = False,
) -> list[DiscoveredFeed]:
    csv_path = _download_catalog(settings, force=force)

    df = pl.read_csv(csv_path, infer_schema_length=0, truncate_ragged_lines=True)

    metro_min_lat, metro_max_lat, metro_min_lon, metro_max_lon = metro.bounds

    df = df.filter(
        (pl.col("data_type") == "gtfs")
        & (pl.col("status") == "active")
        & (pl.col("urls.authentication_type") == "0")
    )

    df = df.filter(
        pl.col("location.bounding_box.minimum_latitude").is_not_null()
        & pl.col("location.bounding_box.maximum_latitude").is_not_null()
        & pl.col("location.bounding_box.minimum_longitude").is_not_null()
        & pl.col("location.bounding_box.maximum_longitude").is_not_null()
    )

    df = df.with_columns(
        pl.col("location.bounding_box.minimum_latitude").cast(pl.Float64).alias("feed_min_lat"),
        pl.col("location.bounding_box.maximum_latitude").cast(pl.Float64).alias("feed_max_lat"),
        pl.col("location.bounding_box.minimum_longitude").cast(pl.Float64).alias("feed_min_lon"),
        pl.col("location.bounding_box.maximum_longitude").cast(pl.Float64).alias("feed_max_lon"),
    )

    df = df.filter(
        (pl.col("feed_max_lat") >= metro_min_lat)
        & (pl.col("feed_min_lat") <= metro_max_lat)
        & (pl.col("feed_max_lon") >= metro_min_lon)
        & (pl.col("feed_min_lon") <= metro_max_lon)
    )

    feeds: list[DiscoveredFeed] = []
    for row in df.iter_rows(named=True):
        feeds.append(
            DiscoveredFeed(
                mdb_id=row["id"],
                provider=row.get("provider", ""),
                download_url=row.get("urls.direct_download", ""),
                stable_url=row.get("urls.latest", ""),
                municipality=row.get("location.municipality", ""),
                subdivision=row.get("location.subdivision_name", ""),
            )
        )

    logger.info("Discovered %d GTFS feeds for %s", len(feeds), metro.metro_id)
    return feeds
