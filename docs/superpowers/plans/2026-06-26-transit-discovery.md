# Transit Discovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace hardcoded GTFS feed URLs with auto-discovery from the Mobility Database CSV catalog, filling transit data gaps in NYC and validating DFW/Chicago coverage.

**Architecture:** New `transit_discovery.py` module downloads the Mobility Database CSV catalog (free, no auth), filters by metro bounding box to find active GTFS feeds. `extract/gtfs.py` calls discovery instead of reading `MetroConfig.gtfs_feeds`. MetroConfig drops `gtfs_feeds`, adds `bounds`.

**Tech Stack:** Python 3.13, polars, requests, pydantic, pytest

**Spec:** `docs/superpowers/specs/2026-06-26-transit-discovery-design.md`

---

### Task 1: Add `bounds` field to MetroConfig

**Files:**
- Modify: `pipeline/src/urbanstack/metro.py`
- Modify: `pipeline/tests/test_metro.py`
- Modify: `pipeline/tests/conftest.py`

- [ ] **Step 1: Write failing test for bounds field**

Add to `pipeline/tests/test_metro.py`:

```python
def test_dfw_bounds() -> None:
    assert len(DFW.bounds) == 4
    min_lat, max_lat, min_lon, max_lon = DFW.bounds
    assert min_lat < max_lat
    assert min_lon < max_lon
    # DFW center (32.78, -96.85) must be inside bounds
    assert min_lat < 32.78 < max_lat
    assert min_lon < -96.85 < max_lon


def test_chicago_bounds() -> None:
    assert len(CHICAGO.bounds) == 4
    min_lat, max_lat, min_lon, max_lon = CHICAGO.bounds
    assert min_lat < 41.88 < max_lat
    assert min_lon < -87.63 < max_lon


def test_nyc_bounds() -> None:
    from urbanstack.metro import NYC
    assert len(NYC.bounds) == 4
    min_lat, max_lat, min_lon, max_lon = NYC.bounds
    assert min_lat < 40.71 < max_lat
    assert min_lon < -74.00 < max_lon
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pipeline && uv run pytest tests/test_metro.py::test_dfw_bounds -v`
Expected: FAIL — `MetroConfig` has no `bounds` field.

- [ ] **Step 3: Add bounds field and values**

In `pipeline/src/urbanstack/metro.py`, add `bounds` to the dataclass and all three metro configs:

```python
@dataclass(frozen=True)
class MetroConfig:
    metro_id: str
    metro_name: str
    metro_fips: str
    states: dict[str, dict[str, str]]
    center: tuple[float, float]
    zoom: int
    bounds: tuple[float, float, float, float]  # (min_lat, max_lat, min_lon, max_lon)
    transit_agencies: dict[str, str]
    gtfs_feeds: dict[str, str]
    umr_names: list[str] = field(default_factory=list)
```

Add bounds to each metro definition:

DFW:
```python
    bounds=(32.25, 33.45, -97.60, -96.00),
```

Chicago:
```python
    bounds=(40.80, 42.50, -88.70, -87.20),
```

NYC:
```python
    bounds=(40.10, 41.60, -74.90, -73.30),
```

Place `bounds=` after `zoom=` and before `transit_agencies=` in each config.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd pipeline && uv run pytest tests/test_metro.py -v`
Expected: All tests PASS including the three new bounds tests.

- [ ] **Step 5: Run /simplify, then commit**

Run `/simplify` on the diff. Then commit:
```bash
git add pipeline/src/urbanstack/metro.py pipeline/tests/test_metro.py
git commit -m "feat: add bounds field to MetroConfig for geographic filtering"
```

---

### Task 2: Create transit discovery module

**Files:**
- Create: `pipeline/src/urbanstack/extract/transit_discovery.py`
- Create: `pipeline/tests/test_extract/test_transit_discovery.py`

- [ ] **Step 1: Write failing tests for discovery module**

Create `pipeline/tests/test_extract/test_transit_discovery.py`:

```python
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from urbanstack.config import Settings
from urbanstack.extract.transit_discovery import DiscoveredFeed, discover_feeds
from urbanstack.metro import DFW


SAMPLE_CSV = textwrap.dedent("""\
    id,data_type,entity_type,location.country_code,location.subdivision_name,location.municipality,provider,is_official,name,note,feed_contact_email,static_reference,urls.direct_download,urls.authentication_type,urls.authentication_info,urls.api_key_parameter_name,urls.latest,urls.license,location.bounding_box.minimum_latitude,location.bounding_box.maximum_latitude,location.bounding_box.minimum_longitude,location.bounding_box.maximum_longitude,location.bounding_box.extracted_on,status,features,redirect.id,redirect.comment
    mdb-152,gtfs,,US,Texas,Dallas,Dallas Area Rapid Transit (DART),True,,,,,,0,,,,32.65,33.10,-97.10,-96.50,,active,Shapes,,
    mdb-885,gtfs,,US,Texas,Fort Worth,Fort Worth Transit Authority (Trinity Metro),True,,,,,,0,,,,32.60,32.95,-97.50,-97.10,,active,Shapes,,
    mdb-999,gtfs,,US,New York,New York,MTA New York City Transit,True,,,,,,0,,,,40.50,40.92,-74.25,-73.70,,active,Shapes,,
    mdb-888,gtfs_rt,vp,US,Texas,Dallas,DART Realtime,True,,,,,,0,,,,,,,,,active,,,
    mdb-777,gtfs,,US,California,Los Angeles,LA Metro,True,,,,,,0,,,,33.70,34.30,-118.70,-117.70,,active,Shapes,,
    mdb-666,gtfs,,US,Texas,Dallas,Inactive Feed,True,,,,,,0,,,,32.70,32.90,-97.00,-96.70,,inactive,Shapes,,
    mdb-555,gtfs,,US,Texas,Dallas,Auth Required Feed,True,,,,,,1,,,,32.70,32.90,-97.00,-96.70,,active,Shapes,,
""")


def _write_catalog(settings: Settings, csv_content: str = SAMPLE_CSV) -> Path:
    catalog_dir = settings.raw_dir / "catalog"
    catalog_dir.mkdir(parents=True, exist_ok=True)
    csv_path = catalog_dir / "feeds_v2.csv"
    csv_path.write_text(csv_content)
    return csv_path


def test_discover_feeds_filters_by_bbox(settings: Settings) -> None:
    _write_catalog(settings)
    with patch("urbanstack.extract.transit_discovery._download_catalog") as mock_dl:
        mock_dl.return_value = settings.raw_dir / "catalog" / "feeds_v2.csv"
        feeds = discover_feeds(settings, DFW)

    provider_names = [f.provider for f in feeds]
    assert "Dallas Area Rapid Transit (DART)" in provider_names
    assert "Fort Worth Transit Authority (Trinity Metro)" in provider_names
    # LA Metro outside DFW bounds
    assert "LA Metro" not in provider_names
    # NYC outside DFW bounds
    assert "MTA New York City Transit" not in provider_names


def test_discover_feeds_excludes_gtfs_rt(settings: Settings) -> None:
    _write_catalog(settings)
    with patch("urbanstack.extract.transit_discovery._download_catalog") as mock_dl:
        mock_dl.return_value = settings.raw_dir / "catalog" / "feeds_v2.csv"
        feeds = discover_feeds(settings, DFW)

    ids = [f.mdb_id for f in feeds]
    assert "mdb-888" not in ids  # GTFS-RT feed


def test_discover_feeds_excludes_inactive(settings: Settings) -> None:
    _write_catalog(settings)
    with patch("urbanstack.extract.transit_discovery._download_catalog") as mock_dl:
        mock_dl.return_value = settings.raw_dir / "catalog" / "feeds_v2.csv"
        feeds = discover_feeds(settings, DFW)

    provider_names = [f.provider for f in feeds]
    assert "Inactive Feed" not in provider_names


def test_discover_feeds_excludes_auth_required(settings: Settings) -> None:
    _write_catalog(settings)
    with patch("urbanstack.extract.transit_discovery._download_catalog") as mock_dl:
        mock_dl.return_value = settings.raw_dir / "catalog" / "feeds_v2.csv"
        feeds = discover_feeds(settings, DFW)

    provider_names = [f.provider for f in feeds]
    assert "Auth Required Feed" not in provider_names


def test_discovered_feed_fields(settings: Settings) -> None:
    _write_catalog(settings)
    with patch("urbanstack.extract.transit_discovery._download_catalog") as mock_dl:
        mock_dl.return_value = settings.raw_dir / "catalog" / "feeds_v2.csv"
        feeds = discover_feeds(settings, DFW)

    dart = next(f for f in feeds if "DART" in f.provider)
    assert dart.mdb_id == "mdb-152"
    assert dart.subdivision == "Texas"
    assert dart.municipality == "Dallas"
    assert isinstance(dart, DiscoveredFeed)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd pipeline && uv run pytest tests/test_extract/test_transit_discovery.py -v`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement transit_discovery.py**

Create `pipeline/src/urbanstack/extract/transit_discovery.py`:

```python
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
CATALOG_MAX_AGE_SECONDS = 86400  # 24 hours


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


def _bboxes_overlap(
    feed_min_lat: float,
    feed_max_lat: float,
    feed_min_lon: float,
    feed_max_lon: float,
    metro_min_lat: float,
    metro_max_lat: float,
    metro_min_lon: float,
    metro_max_lon: float,
) -> bool:
    if feed_max_lat < metro_min_lat or feed_min_lat > metro_max_lat:
        return False
    if feed_max_lon < metro_min_lon or feed_min_lon > metro_max_lon:
        return False
    return True


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

    logger.info(
        "Discovered %d GTFS feeds for %s", len(feeds), metro.metro_id,
    )
    return feeds
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd pipeline && uv run pytest tests/test_extract/test_transit_discovery.py -v`
Expected: All 5 tests PASS.

- [ ] **Step 5: Run /simplify, then commit**

Run `/simplify` on the diff. Then commit:
```bash
git add pipeline/src/urbanstack/extract/transit_discovery.py pipeline/tests/test_extract/test_transit_discovery.py
git commit -m "feat: add transit discovery module using Mobility Database CSV catalog"
```

---

### Task 3: Update GTFS extract to use discovery

**Files:**
- Modify: `pipeline/src/urbanstack/extract/gtfs.py`
- Modify: `pipeline/tests/test_extract/test_gtfs.py`

- [ ] **Step 1: Write failing test for discovery-based extraction**

Add to `pipeline/tests/test_extract/test_gtfs.py`:

```python
from urbanstack.extract.transit_discovery import DiscoveredFeed


def test_extract_uses_discovery(settings: Settings, metro: MetroConfig) -> None:
    """extract_gtfs should call discover_feeds and download from discovered URLs."""
    discovered = [
        DiscoveredFeed(
            mdb_id="mdb-152",
            provider="Test Agency",
            download_url="https://example.com/gtfs.zip",
            stable_url="https://files.mobilitydatabase.org/mdb-152/latest.zip",
            municipality="Dallas",
            subdivision="Texas",
        ),
    ]

    raw_dir = settings.metro_raw_dir(metro.metro_id) / "gtfs"
    raw_dir.mkdir(parents=True, exist_ok=True)
    zip_path = raw_dir / "test_agency_gtfs.zip"
    zip_path.write_bytes(_make_gtfs_zip())

    with (
        patch("urbanstack.extract.gtfs.discover_feeds", return_value=discovered),
        patch("urbanstack.extract.gtfs.requests.get") as mock_get,
    ):
        mock_get.side_effect = AssertionError("Should use cached zip")
        result = extract_gtfs(settings, metro)

    assert len(result["routes"]) == 2
    agencies = result["routes"]["agency"].unique().to_list()
    assert "Test Agency" in agencies
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pipeline && uv run pytest tests/test_extract/test_gtfs.py::test_extract_uses_discovery -v`
Expected: FAIL — `extract_gtfs` still reads from `metro.gtfs_feeds`, not discovery.

- [ ] **Step 3: Update extract_gtfs to use discovery**

Modify `pipeline/src/urbanstack/extract/gtfs.py`:

Add import at top:
```python
from urbanstack.extract.transit_discovery import DiscoveredFeed, discover_feeds
```

Replace the `extract_gtfs` function signature and body. Remove `agencies` parameter. Replace feed iteration logic:

```python
def extract_gtfs(
    settings: Settings,
    metro: MetroConfig,
    *,
    force: bool = False,
) -> dict[str, pl.DataFrame]:
    """Extract GTFS data for a metro's transit agencies via auto-discovery."""
    parquet_dir = settings.metro_staging_dir(metro.metro_id) / "gtfs"
    routes_path = parquet_dir / "gtfs_routes.parquet"
    stops_path = parquet_dir / "gtfs_stops.parquet"
    shapes_path = parquet_dir / "gtfs_shapes.parquet"

    if all(p.exists() for p in (routes_path, stops_path, shapes_path)) and not force:
        logger.info("GTFS parquets exist, skipping extraction")
        return {
            "routes": pl.read_parquet(routes_path),
            "stops": pl.read_parquet(stops_path),
            "shapes": pl.read_parquet(shapes_path),
        }

    raw_dir = settings.metro_raw_dir(metro.metro_id) / "gtfs"
    raw_dir.mkdir(parents=True, exist_ok=True)

    discovered = discover_feeds(settings, metro, force=force)

    all_routes: list[GtfsRoute] = []
    all_stops: list[GtfsStop] = []
    all_shapes: list[GtfsShape] = []

    for feed in discovered:
        url = feed.download_url or feed.stable_url
        if not url:
            logger.warning("No download URL for %s (%s), skipping", feed.provider, feed.mdb_id)
            continue

        agency = feed.provider

        try:
            zip_path = _download_feed(agency, url, raw_dir, force=force)

            route_rows = _read_csv_from_zip(zip_path, "routes.txt")
            stop_rows = _read_csv_from_zip(zip_path, "stops.txt")
            shape_rows = _read_csv_from_zip(zip_path, "shapes.txt")
        except (requests.RequestException, zipfile.BadZipFile, OSError, UnicodeDecodeError) as exc:
            logger.warning("Skipping %s: %s", agency, exc)
            continue

        all_routes.extend(_parse_routes(agency, route_rows))
        all_stops.extend(_parse_stops(agency, stop_rows))
        all_shapes.extend(_parse_shapes(agency, shape_rows))

        logger.info(
            "%s: %d routes, %d stops, %d shape points",
            agency,
            len(route_rows),
            len(stop_rows),
            len(shape_rows),
        )

    routes_df = _records_to_df(all_routes)
    stops_df = _records_to_df(all_stops)
    shapes_df = _records_to_df(all_shapes)

    parquet_dir.mkdir(parents=True, exist_ok=True)
    if len(routes_df) > 0:
        routes_df.write_parquet(routes_path)
    if len(stops_df) > 0:
        stops_df.write_parquet(stops_path)
    if len(shapes_df) > 0:
        shapes_df.write_parquet(shapes_path)

    logger.info(
        "GTFS totals: %d routes, %d stops, %d shape points",
        len(routes_df),
        len(stops_df),
        len(shapes_df),
    )

    return {
        "routes": routes_df,
        "stops": stops_df,
        "shapes": shapes_df,
    }
```

- [ ] **Step 4: Update existing tests**

Several existing tests pass `agencies=["DART"]` which no longer exists. Update them to mock `discover_feeds` instead.

Replace the `_place_zip` helper and update tests in `test_gtfs.py`:

```python
from urbanstack.extract.transit_discovery import DiscoveredFeed

DART_FEED = DiscoveredFeed(
    mdb_id="mdb-152",
    provider="DART",
    download_url="https://example.com/dart.zip",
    stable_url="",
    municipality="Dallas",
    subdivision="Texas",
)

TRINITY_FEED = DiscoveredFeed(
    mdb_id="mdb-885",
    provider="Trinity Metro",
    download_url="https://example.com/trinity.zip",
    stable_url="",
    municipality="Fort Worth",
    subdivision="Texas",
)


def _place_zip(settings: Settings, metro: MetroConfig, agency: str = "DART") -> Path:
    raw_dir = settings.metro_raw_dir(metro.metro_id) / "gtfs"
    raw_dir.mkdir(parents=True, exist_ok=True)
    zip_path = raw_dir / f"{agency.lower().replace(' ', '_')}_gtfs.zip"
    zip_path.write_bytes(_make_gtfs_zip())
    return zip_path
```

Update each test that used `agencies=["DART"]` to instead patch `discover_feeds`:

For `test_extract_single_agency`:
```python
def test_extract_single_agency(settings: Settings, metro: MetroConfig) -> None:
    _place_zip(settings, metro, "DART")

    with (
        patch("urbanstack.extract.gtfs.discover_feeds", return_value=[DART_FEED]),
        patch("urbanstack.extract.gtfs.requests.get") as mock_get,
    ):
        mock_get.side_effect = AssertionError("Should not download")
        result = extract_gtfs(settings, metro)

    assert "routes" in result
    assert "stops" in result
    assert "shapes" in result
    assert len(result["routes"]) == 2
    assert len(result["stops"]) == 2
    assert len(result["shapes"]) == 3
```

For `test_route_contract`:
```python
def test_route_contract(settings: Settings, metro: MetroConfig) -> None:
    _place_zip(settings, metro, "DART")

    with (
        patch("urbanstack.extract.gtfs.discover_feeds", return_value=[DART_FEED]),
        patch("urbanstack.extract.gtfs.requests.get"),
    ):
        result = extract_gtfs(settings, metro)

    row = result["routes"].to_dicts()[0]
    record = GtfsRoute.model_validate(row)
    assert record.agency == "DART"
    assert record.route_id == "R1"
    assert record.route_type == 3
```

For `test_stop_contract`:
```python
def test_stop_contract(settings: Settings, metro: MetroConfig) -> None:
    _place_zip(settings, metro, "DART")

    with (
        patch("urbanstack.extract.gtfs.discover_feeds", return_value=[DART_FEED]),
        patch("urbanstack.extract.gtfs.requests.get"),
    ):
        result = extract_gtfs(settings, metro)

    row = result["stops"].to_dicts()[0]
    record = GtfsStop.model_validate(row)
    assert record.agency == "DART"
    assert record.stop_id == "S1"
    assert record.latitude == pytest.approx(32.7767)
    assert record.longitude == pytest.approx(-96.7970)
```

For `test_shape_contract`:
```python
def test_shape_contract(settings: Settings, metro: MetroConfig) -> None:
    _place_zip(settings, metro, "DART")

    with (
        patch("urbanstack.extract.gtfs.discover_feeds", return_value=[DART_FEED]),
        patch("urbanstack.extract.gtfs.requests.get"),
    ):
        result = extract_gtfs(settings, metro)

    row = result["shapes"].to_dicts()[0]
    record = GtfsShape.model_validate(row)
    assert record.agency == "DART"
    assert record.shape_id == "SH1"
    assert record.sequence == 1
```

For `test_idempotent_skip`:
```python
def test_idempotent_skip(settings: Settings, metro: MetroConfig) -> None:
    parquet_dir = settings.metro_staging_dir(metro.metro_id) / "gtfs"
    parquet_dir.mkdir(parents=True, exist_ok=True)
    for name in ("gtfs_routes.parquet", "gtfs_stops.parquet", "gtfs_shapes.parquet"):
        pl.DataFrame({"agency": ["DART"]}).write_parquet(parquet_dir / name)

    with patch("urbanstack.extract.gtfs.discover_feeds") as mock_discover:
        result = extract_gtfs(settings, metro)
        mock_discover.assert_not_called()

    assert len(result["routes"]) == 1
```

For `test_force_overwrite`:
```python
def test_force_overwrite(settings: Settings, metro: MetroConfig) -> None:
    _place_zip(settings, metro, "DART")
    parquet_dir = settings.metro_staging_dir(metro.metro_id) / "gtfs"
    parquet_dir.mkdir(parents=True, exist_ok=True)
    for name in ("gtfs_routes.parquet", "gtfs_stops.parquet", "gtfs_shapes.parquet"):
        pl.DataFrame({"agency": ["old"]}).write_parquet(parquet_dir / name)

    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.content = _make_gtfs_zip()

    with (
        patch("urbanstack.extract.gtfs.discover_feeds", return_value=[DART_FEED]),
        patch("urbanstack.extract.gtfs.requests.get", return_value=mock_resp),
    ):
        result = extract_gtfs(settings, metro, force=True)

    assert "old" not in result["routes"]["agency"].to_list()
    assert len(result["routes"]) == 2
```

For `test_download_on_missing_zip`:
```python
def test_download_on_missing_zip(settings: Settings, metro: MetroConfig) -> None:
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.content = _make_gtfs_zip()

    with (
        patch("urbanstack.extract.gtfs.discover_feeds", return_value=[DART_FEED]),
        patch("urbanstack.extract.gtfs.requests.get", return_value=mock_resp),
    ):
        result = extract_gtfs(settings, metro)

    assert len(result["routes"]) == 2
    zip_path = settings.metro_raw_dir(metro.metro_id) / "gtfs" / "dart_gtfs.zip"
    assert zip_path.exists()
```

Remove `test_unknown_agency_raises` — no longer applicable (discovery replaces hardcoded list).

For `test_null_lat_lon_skipped`:
```python
def test_null_lat_lon_skipped(settings: Settings, metro: MetroConfig) -> None:
    stops = (
        "stop_id,stop_name,stop_lat,stop_lon\n"
        "S1,Good Stop,32.7767,-96.7970\n"
        "S2,Bad Stop,,\n"
        "S3,Zero Stop,0.0,0.0\n"
    )
    raw_dir = settings.metro_raw_dir(metro.metro_id) / "gtfs"
    raw_dir.mkdir(parents=True, exist_ok=True)
    zip_path = raw_dir / "dart_gtfs.zip"
    zip_path.write_bytes(_make_gtfs_zip(stops=stops))

    with (
        patch("urbanstack.extract.gtfs.discover_feeds", return_value=[DART_FEED]),
        patch("urbanstack.extract.gtfs.requests.get"),
    ):
        result = extract_gtfs(settings, metro)

    stop_ids = result["stops"]["stop_id"].to_list()
    assert "S1" in stop_ids
    assert "S2" not in stop_ids
    assert "S3" not in stop_ids
```

For `test_parquets_saved`:
```python
def test_parquets_saved(settings: Settings, metro: MetroConfig) -> None:
    _place_zip(settings, metro, "DART")

    with (
        patch("urbanstack.extract.gtfs.discover_feeds", return_value=[DART_FEED]),
        patch("urbanstack.extract.gtfs.requests.get"),
    ):
        extract_gtfs(settings, metro)

    for name in ("gtfs_routes.parquet", "gtfs_stops.parquet", "gtfs_shapes.parquet"):
        assert (settings.metro_staging_dir(metro.metro_id) / "gtfs" / name).exists()
```

For `test_multiple_agencies`:
```python
def test_multiple_agencies(settings: Settings, metro: MetroConfig) -> None:
    _place_zip(settings, metro, "DART")
    raw_dir = settings.metro_raw_dir(metro.metro_id) / "gtfs"
    zip_path = raw_dir / "trinity_metro_gtfs.zip"
    routes = (
        "route_id,route_short_name,route_long_name,route_type\n"
        "TM1,5,Fifth Ave,3\n"
    )
    zip_path.write_bytes(_make_gtfs_zip(routes=routes))

    with (
        patch("urbanstack.extract.gtfs.discover_feeds", return_value=[DART_FEED, TRINITY_FEED]),
        patch("urbanstack.extract.gtfs.requests.get"),
    ):
        result = extract_gtfs(settings, metro)

    agencies = result["routes"]["agency"].unique().to_list()
    assert "DART" in agencies
    assert "Trinity Metro" in agencies
    assert len(result["routes"]) == 3
```

- [ ] **Step 5: Run all GTFS tests**

Run: `cd pipeline && uv run pytest tests/test_extract/test_gtfs.py -v`
Expected: All tests PASS.

- [ ] **Step 6: Run /simplify, then commit**

Run `/simplify` on the diff. Then commit:
```bash
git add pipeline/src/urbanstack/extract/gtfs.py pipeline/tests/test_extract/test_gtfs.py
git commit -m "refactor: extract_gtfs uses transit discovery instead of hardcoded feeds"
```

---

### Task 4: Remove gtfs_feeds from MetroConfig

**Files:**
- Modify: `pipeline/src/urbanstack/metro.py`
- Modify: `pipeline/tests/test_metro.py`

- [ ] **Step 1: Remove gtfs_feeds field from MetroConfig dataclass**

In `pipeline/src/urbanstack/metro.py`:

Remove the `gtfs_feeds: dict[str, str]` field from the dataclass.

Remove the `gtfs_feeds={...}` blocks from DFW, CHICAGO, and NYC configs.

The dataclass becomes:
```python
@dataclass(frozen=True)
class MetroConfig:
    metro_id: str
    metro_name: str
    metro_fips: str
    states: dict[str, dict[str, str]]
    center: tuple[float, float]
    zoom: int
    bounds: tuple[float, float, float, float]
    transit_agencies: dict[str, str]
    umr_names: list[str] = field(default_factory=list)
```

- [ ] **Step 2: Update conftest.py metro fixture**

The `conftest.py` uses `DFW` directly which no longer has `gtfs_feeds`. Since the field is removed from the dataclass, this should work without changes. Verify by running:

Run: `cd pipeline && uv run pytest tests/conftest.py --collect-only`
Expected: Collection succeeds, no import errors.

- [ ] **Step 3: Run full test suite**

Run: `cd pipeline && uv run pytest -v`
Expected: All tests PASS. No remaining references to `metro.gtfs_feeds`.

- [ ] **Step 4: Verify no remaining references**

Run: `grep -rn "gtfs_feeds" --include="*.py" pipeline/`
Expected: No matches (or only in test_transit_discovery.py sample data if applicable).

- [ ] **Step 5: Run /simplify, then commit**

Run `/simplify` on the diff. Then commit:
```bash
git add pipeline/src/urbanstack/metro.py
git commit -m "refactor: remove gtfs_feeds from MetroConfig (replaced by transit discovery)"
```

---

### Task 5: Run full test suite and validate

**Files:**
- None (validation only)

- [ ] **Step 1: Run linter**

Run: `cd pipeline && uv run ruff check src/ tests/`
Expected: No errors.

- [ ] **Step 2: Run formatter check**

Run: `cd pipeline && uv run ruff format --check src/ tests/`
Expected: No formatting issues.

- [ ] **Step 3: Run full test suite**

Run: `cd pipeline && uv run pytest -v`
Expected: All tests PASS.

- [ ] **Step 4: Verify discovery module works with real catalog (manual smoke test)**

Run a quick smoke test to verify the catalog downloads and filters correctly:

```python
cd pipeline && uv run python -c "
from urbanstack.config import load_settings
from urbanstack.metro import DFW, CHICAGO, NYC
from urbanstack.extract.transit_discovery import discover_feeds

settings = load_settings()
for metro in [DFW, CHICAGO, NYC]:
    feeds = discover_feeds(settings, metro)
    print(f'{metro.metro_id}: {len(feeds)} feeds')
    for f in feeds:
        print(f'  {f.mdb_id}: {f.provider}')
    print()
"
```

Expected: DFW shows 3-4 feeds, Chicago shows 3-5 feeds, NYC shows 10-15 feeds.

- [ ] **Step 5: Commit spec and plan**

```bash
git add docs/superpowers/specs/2026-06-26-transit-discovery-design.md docs/superpowers/plans/2026-06-26-transit-discovery.md
git commit -m "docs: add transit discovery spec and implementation plan"
```
