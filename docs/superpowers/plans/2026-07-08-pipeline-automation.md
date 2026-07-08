# Pipeline Automation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make adding a metro a single-file-edit + single-command operation with validation.

**Architecture:** Add `region` field to `MetroConfig`, auto-generate `metro.ts` from Python registry, move transit GeoJSON script into CLI, add `pipeline`/`validate`/`sync-web` commands that orchestrate the full flow.

**Tech Stack:** Python 3.13, argparse CLI, polars, TypeScript codegen via string templates

**Spec:** `docs/superpowers/specs/2026-07-08-pipeline-automation-design.md`

---

## File Structure

| File | Action | Purpose |
|------|--------|---------|
| `pipeline/src/urbanstack/metro.py` | Modify | Add `RegionMeta` dataclass, `region` field to `MetroConfig`, `REGION_CONFIGS` dict |
| `pipeline/src/urbanstack/sync_web.py` | Create | Generate `metro.ts` from Python registries |
| `pipeline/src/urbanstack/validate.py` | Create | Validation report for metro data completeness |
| `pipeline/src/urbanstack/transit_geojson.py` | Create | Transit GeoJSON builder (moved from `scripts/build_transit_geojson.py`) |
| `pipeline/src/urbanstack/cli.py` | Modify | Add `pipeline`, `transit-geojson`, `sync-web`, `validate` commands |
| `web/src/lib/metro.ts` | Auto-generated | No manual edits after this |
| `pipeline/tests/test_metro.py` | Modify | Add tests for region fields |
| `pipeline/tests/test_sync_web.py` | Create | Test metro.ts generation |
| `pipeline/tests/test_validate.py` | Create | Test validation report |

---

### Task 1: Add `RegionMeta` and `region` field to `MetroConfig`

**Files:**
- Modify: `pipeline/src/urbanstack/metro.py`
- Modify: `pipeline/tests/test_metro.py`

- [ ] **Step 1: Write failing tests for region support**

Add to `pipeline/tests/test_metro.py`:

```python
from urbanstack.metro import METRO_REGISTRY, REGION_CONFIGS, RegionMeta


def test_region_meta_fields() -> None:
    texas = REGION_CONFIGS["texas"]
    assert isinstance(texas, RegionMeta)
    assert texas.region_name == "Texas"
    assert len(texas.center) == 2
    assert texas.zoom > 0


def test_all_metros_have_region() -> None:
    for metro_id, metro in METRO_REGISTRY.items():
        assert metro.region, f"{metro_id} missing region"
        assert metro.region in REGION_CONFIGS, f"{metro_id} region '{metro.region}' not in REGION_CONFIGS"


def test_region_configs_cover_all_regions() -> None:
    regions_used = {m.region for m in METRO_REGISTRY.values()}
    for r in regions_used:
        assert r in REGION_CONFIGS, f"Region '{r}' used by a metro but not in REGION_CONFIGS"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd pipeline && uv run pytest tests/test_metro.py -v -k "region"`
Expected: FAIL — `RegionMeta` not importable, `region` attribute missing

- [ ] **Step 3: Implement `RegionMeta` and add `region` field**

In `pipeline/src/urbanstack/metro.py`, add after the `MetroConfig` class (before the metro instances):

```python
@dataclass(frozen=True)
class RegionMeta:
    region_name: str
    center: tuple[float, float]
    zoom: int
```

Add `region` field to `MetroConfig`:

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
    region: str = ""
```

Add `region=` to each metro instance:
- `DFW`: `region="texas"`
- `CHICAGO`: `region="midwest"`
- `NYC`: `region="northeast"`
- `HOUSTON`: `region="texas"`
- `AUSTIN`: `region="texas"`
- `SAN_ANTONIO`: `region="texas"`
- `BOSTON`: `region="northeast"`
- `DENVER`: `region="mountain"`
- `CHEYENNE`: `region="mountain"`

Add `REGION_CONFIGS` after `METRO_REGISTRY`:

```python
REGION_CONFIGS: dict[str, RegionMeta] = {
    "texas": RegionMeta(region_name="Texas", center=(30.5, -97.0), zoom=6),
    "northeast": RegionMeta(region_name="Northeast", center=(41.5, -72.5), zoom=6),
    "midwest": RegionMeta(region_name="Midwest", center=(41.88, -87.63), zoom=7),
    "mountain": RegionMeta(region_name="Mountain", center=(40.44, -104.90), zoom=7),
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd pipeline && uv run pytest tests/test_metro.py -v`
Expected: All tests PASS including new region tests

- [ ] **Step 5: Commit**

```bash
git add pipeline/src/urbanstack/metro.py pipeline/tests/test_metro.py
git commit -m "feat: add region field to MetroConfig and RegionMeta dataclass"
```

---

### Task 2: Create `sync_web.py` — auto-generate `metro.ts`

**Files:**
- Create: `pipeline/src/urbanstack/sync_web.py`
- Create: `pipeline/tests/test_sync_web.py`

- [ ] **Step 1: Write failing test**

Create `pipeline/tests/test_sync_web.py`:

```python
from urbanstack.sync_web import generate_metro_ts


def test_generate_metro_ts_has_header() -> None:
    output = generate_metro_ts()
    assert "AUTO-GENERATED" in output
    assert "do not edit manually" in output


def test_generate_metro_ts_has_metros() -> None:
    output = generate_metro_ts()
    assert "export const METROS" in output
    assert '"dfw"' in output or "dfw:" in output
    assert '"cheyenne"' in output or "cheyenne:" in output


def test_generate_metro_ts_has_regions() -> None:
    output = generate_metro_ts()
    assert "export const REGIONS" in output
    assert '"texas"' in output or "texas:" in output
    assert '"mountain"' in output or "mountain:" in output


def test_generate_metro_ts_has_metro_to_region() -> None:
    output = generate_metro_ts()
    assert "METRO_TO_REGION" in output


def test_generate_metro_ts_metros_sorted_alphabetically() -> None:
    output = generate_metro_ts()
    lines = output.split("\n")
    metro_keys = []
    for line in lines:
        stripped = line.strip()
        if stripped.endswith("{") and ":" in stripped and "export" not in stripped:
            key = stripped.split(":")[0].strip()
            if key and not key.startswith("//") and not key.startswith("metro_") and not key.startswith("region_"):
                metro_keys.append(key)
    # Find the METROS block keys specifically
    in_metros = False
    metros_order = []
    for line in lines:
        if "export const METROS" in line:
            in_metros = True
            continue
        if in_metros and line.strip().startswith("}"):
            break
        if in_metros:
            stripped = line.strip()
            if stripped.endswith("{") and ":" in stripped:
                metros_order.append(stripped.split(":")[0].strip())
    assert metros_order == sorted(metros_order), f"METROS not sorted: {metros_order}"


def test_generate_metro_ts_region_metro_ids_derived() -> None:
    output = generate_metro_ts()
    assert "denver" in output
    assert "cheyenne" in output
    # Mountain region should contain both denver and cheyenne
    assert "mountain" in output


def test_generate_metro_ts_valid_typescript_syntax() -> None:
    output = generate_metro_ts()
    # Basic structural checks
    assert output.count("export interface MetroConfig") == 1
    assert output.count("export interface RegionConfig") == 1
    assert output.count("export const METROS") == 1
    assert output.count("export const REGIONS") == 1
    assert output.count("export const METRO_TO_REGION") == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd pipeline && uv run pytest tests/test_sync_web.py -v`
Expected: FAIL — `sync_web` module not found

- [ ] **Step 3: Implement `sync_web.py`**

Create `pipeline/src/urbanstack/sync_web.py`:

```python
"""Generate web/src/lib/metro.ts from the Python metro registry."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from urbanstack.metro import METRO_REGISTRY, REGION_CONFIGS

logger = logging.getLogger("urbanstack.sync_web")

HEADER = """\
// AUTO-GENERATED from pipeline/src/urbanstack/metro.py — do not edit manually
// Regenerate: cd pipeline && uv run python -m urbanstack.cli sync-web
"""


def generate_metro_ts() -> str:
    lines = [HEADER]

    # MetroConfig interface
    lines.append("export interface MetroConfig {")
    lines.append("  metro_id: string;")
    lines.append("  metro_name: string;")
    lines.append("  center: [number, number];")
    lines.append("  zoom: number;")
    lines.append("}")
    lines.append("")

    # METROS dict — sorted alphabetically
    lines.append("export const METROS: Record<string, MetroConfig> = {")
    for metro_id in sorted(METRO_REGISTRY):
        m = METRO_REGISTRY[metro_id]
        lines.append(f"  {metro_id}: {{")
        lines.append(f"    metro_id: {json.dumps(metro_id)},")
        lines.append(f"    metro_name: {json.dumps(m.metro_name)},")
        lines.append(f"    center: [{m.center[0]}, {m.center[1]}],")
        lines.append(f"    zoom: {m.zoom},")
        lines.append("  },")
    lines.append("};")
    lines.append("")

    # RegionConfig interface
    lines.append("export interface RegionConfig {")
    lines.append("  region_id: string;")
    lines.append("  region_name: string;")
    lines.append("  metro_ids: string[];")
    lines.append("  center: [number, number];")
    lines.append("  zoom: number;")
    lines.append("}")
    lines.append("")

    # Build region -> metro_ids mapping from metro configs
    region_metros: dict[str, list[str]] = {}
    for metro_id in sorted(METRO_REGISTRY):
        m = METRO_REGISTRY[metro_id]
        if m.region:
            region_metros.setdefault(m.region, []).append(metro_id)

    # REGIONS dict — sorted alphabetically
    lines.append("export const REGIONS: Record<string, RegionConfig> = {")
    for region_id in sorted(REGION_CONFIGS):
        rc = REGION_CONFIGS[region_id]
        metro_ids = region_metros.get(region_id, [])
        ids_str = ", ".join(json.dumps(mid) for mid in metro_ids)
        lines.append(f"  {region_id}: {{")
        lines.append(f"    region_id: {json.dumps(region_id)},")
        lines.append(f"    region_name: {json.dumps(rc.region_name)},")
        lines.append(f"    metro_ids: [{ids_str}],")
        lines.append(f"    center: [{rc.center[0]}, {rc.center[1]}],")
        lines.append(f"    zoom: {rc.zoom},")
        lines.append("  },")
    lines.append("};")
    lines.append("")

    # METRO_TO_REGION derived lookup
    lines.append("export const METRO_TO_REGION: Record<string, string> = {};")
    lines.append("for (const [regionId, config] of Object.entries(REGIONS)) {")
    lines.append("  for (const metroId of config.metro_ids) {")
    lines.append("    METRO_TO_REGION[metroId] = regionId;")
    lines.append("  }")
    lines.append("}")
    lines.append("")

    return "\n".join(lines)


def sync_web(web_root: Path) -> None:
    output = generate_metro_ts()
    target = web_root / "src" / "lib" / "metro.ts"
    target.write_text(output)
    logger.info("Wrote %s (%d bytes)", target, len(output))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd pipeline && uv run pytest tests/test_sync_web.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline/src/urbanstack/sync_web.py pipeline/tests/test_sync_web.py
git commit -m "feat: add sync_web module to auto-generate metro.ts from Python registry"
```

---

### Task 3: Create `validate.py` — metro data validation report

**Files:**
- Create: `pipeline/src/urbanstack/validate.py`
- Create: `pipeline/tests/test_validate.py`

- [ ] **Step 1: Write failing test**

Create `pipeline/tests/test_validate.py`:

```python
from pathlib import Path

from urbanstack.validate import MetroReport, check_file, check_parquet


def test_check_file_exists(tmp_path: Path) -> None:
    f = tmp_path / "test.geojson"
    f.write_text('{"type": "FeatureCollection", "features": []}')
    result = check_file(f)
    assert result.exists is True
    assert result.size_bytes > 0


def test_check_file_missing(tmp_path: Path) -> None:
    result = check_file(tmp_path / "missing.geojson")
    assert result.exists is False


def test_check_parquet_missing(tmp_path: Path) -> None:
    result = check_parquet(tmp_path / "missing.parquet")
    assert result.exists is False
    assert result.row_count == 0


def test_metro_report_has_warnings() -> None:
    report = MetroReport(metro_id="test", metro_name="Test MSA")
    report.add_warning("UMR data missing")
    assert len(report.warnings) == 1
    assert report.ok is True  # warnings don't fail


def test_metro_report_has_errors() -> None:
    report = MetroReport(metro_id="test", metro_name="Test MSA")
    report.add_error("County mart missing")
    assert len(report.errors) == 1
    assert report.ok is False  # errors fail
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd pipeline && uv run pytest tests/test_validate.py -v`
Expected: FAIL — `validate` module not found

- [ ] **Step 3: Implement `validate.py`**

Create `pipeline/src/urbanstack/validate.py`:

```python
"""Validation report for metro data completeness."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import polars as pl

from urbanstack.metro import METRO_REGISTRY, MetroConfig

logger = logging.getLogger("urbanstack.validate")

STAGING_SOURCES = [
    ("acs", "acs/acs_county_*.parquet", "acs/acs_block_group_*.parquet"),
    ("fars", "fars/fars_*.parquet", None),
    ("ntd", "ntd/ntd_*.parquet", None),
    ("umr", "umr/umr_*.parquet", None),
    ("fhwa", "fhwa/fhwa_*.parquet", None),
    ("epa_sld", "epa_sld/epa_sld_*.parquet", None),
    ("gazetteer", "gazetteer/gazetteer_*.parquet", None),
    ("usaspending", "usaspending/usaspending_*.parquet", None),
    ("tmas_stations", "tmas_stations/tmas_stations_*.parquet", None),
    ("osm_parks", "osm_parks/osm_parks_*.parquet", None),
]

OPTIONAL_SOURCES = {"umr"}


@dataclass
class FileCheck:
    exists: bool
    size_bytes: int = 0
    row_count: int = 0


@dataclass
class MetroReport:
    metro_id: str
    metro_name: str
    sources: dict[str, FileCheck] = field(default_factory=dict)
    marts: dict[str, FileCheck] = field(default_factory=dict)
    files: dict[str, FileCheck] = field(default_factory=dict)
    null_columns: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)


def check_file(path: Path) -> FileCheck:
    if not path.exists():
        return FileCheck(exists=False)
    return FileCheck(exists=True, size_bytes=path.stat().st_size)


def check_parquet(path: Path) -> FileCheck:
    if not path.exists():
        return FileCheck(exists=False)
    try:
        df = pl.scan_parquet(path).collect()
        return FileCheck(exists=True, size_bytes=path.stat().st_size, row_count=len(df))
    except Exception:
        return FileCheck(exists=True, size_bytes=path.stat().st_size, row_count=0)


def _find_parquet(directory: Path, pattern: str) -> Path | None:
    matches = list(directory.glob(pattern))
    return matches[0] if matches else None


def _find_null_columns(parquet_path: Path) -> list[str]:
    try:
        df = pl.read_parquet(parquet_path)
        return [col for col in df.columns if df[col].null_count() == len(df)]
    except Exception:
        return []


def validate_metro(
    metro: MetroConfig,
    settings: "Settings",
    *,
    web_ts_path: Path | None = None,
) -> MetroReport:
    from urbanstack.config import Settings

    report = MetroReport(metro_id=metro.metro_id, metro_name=metro.metro_name)
    staging = settings.metro_staging_dir(metro.metro_id)
    marts = settings.metro_marts_dir(metro.metro_id)
    web_dir = settings.web_data_dir(metro.metro_id)

    # Check staging sources
    for name, county_pattern, bg_pattern in STAGING_SOURCES:
        pq = _find_parquet(staging, county_pattern)
        if pq:
            fc = check_parquet(pq)
            report.sources[name] = fc
        else:
            report.sources[name] = FileCheck(exists=False)
            if name in OPTIONAL_SOURCES:
                report.add_warning(f"{name} data missing (optional)")
            else:
                report.add_warning(f"{name} staging data missing")

    # Check marts
    for mart_name in ["county_summary", "block_group_summary", "metro_summary"]:
        pq = marts / f"{mart_name}.parquet"
        fc = check_parquet(pq)
        report.marts[mart_name] = fc
        if not fc.exists:
            report.add_error(f"{mart_name} mart missing")

    # Check boundary GeoJSON
    for geojson_name in ["counties.geojson", "block_groups.geojson"]:
        fc = check_file(web_dir / geojson_name)
        report.files[geojson_name] = fc
        if not fc.exists:
            report.add_error(f"{geojson_name} missing")

    # Check transit GeoJSON
    for transit_name in ["transit_routes.geojson.gz", "transit_stops.geojson.gz"]:
        fc = check_file(web_dir / transit_name)
        report.files[transit_name] = fc
        if not fc.exists:
            report.add_warning(f"{transit_name} missing")

    # Check PMTiles
    pmtiles = settings.exports_dir / f"{metro.metro_id}_block_groups.pmtiles"
    fc = check_file(pmtiles)
    report.files["pmtiles"] = fc
    if not fc.exists:
        report.add_warning("PMTiles not exported (run export or install tippecanoe)")

    # Check null columns in county mart
    county_pq = marts / "county_summary.parquet"
    if county_pq.exists():
        report.null_columns = _find_null_columns(county_pq)

    # Check metro.ts sync
    if web_ts_path and web_ts_path.exists():
        content = web_ts_path.read_text()
        if metro.metro_id not in content:
            report.add_error(f"metro.ts missing {metro.metro_id} — run sync-web")
        else:
            report.files["metro.ts"] = FileCheck(exists=True)

    return report


def format_report(report: MetroReport) -> str:
    lines = [f"═══ {report.metro_name} ═══"]

    for name, fc in report.sources.items():
        status = "✓" if fc.exists else "—"
        row_info = f"{fc.row_count:,} rows" if fc.row_count else "missing"
        lines.append(f"  {name:<16} {row_info:<30} {status}")

    for name, fc in report.marts.items():
        label = name.replace("_summary", "")
        status = "✓" if fc.exists else "✗"
        lines.append(f"  {label:<16} {'exists' if fc.exists else 'MISSING':<30} {status}")

    for name, fc in report.files.items():
        status = "✓" if fc.exists else "—"
        if fc.size_bytes > 1_000_000:
            size = f"{fc.size_bytes / 1e6:.1f} MB"
        elif fc.size_bytes > 0:
            size = f"{fc.size_bytes / 1024:.0f} KB"
        else:
            size = "missing"
        lines.append(f"  {name:<16} {size:<30} {status}")

    if report.null_columns:
        lines.append(f"  Null columns:  {', '.join(report.null_columns)}")

    for w in report.warnings:
        lines.append(f"  ⚠ {w}")
    for e in report.errors:
        lines.append(f"  ✗ {e}")

    status = "PASS" if report.ok else "FAIL"
    lines.append(f"  Result: {status}")
    return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd pipeline && uv run pytest tests/test_validate.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline/src/urbanstack/validate.py pipeline/tests/test_validate.py
git commit -m "feat: add validate module for metro data completeness reports"
```

---

### Task 4: Move transit GeoJSON into CLI module

**Files:**
- Create: `pipeline/src/urbanstack/transit_geojson.py`
- Modify: `pipeline/scripts/build_transit_geojson.py` (thin wrapper)

- [ ] **Step 1: Create the module**

Create `pipeline/src/urbanstack/transit_geojson.py` by extracting the core logic from `scripts/build_transit_geojson.py`. The new module exposes a single function:

```python
"""Build transit route/stop GeoJSON from GTFS feeds."""

from __future__ import annotations

import gzip
import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from urbanstack.config import Settings
    from urbanstack.metro import MetroConfig

logger = logging.getLogger("urbanstack.transit_geojson")


def build_transit_geojson(
    settings: Settings,
    metro: MetroConfig,
    *,
    force: bool = False,
) -> dict[str, int]:
    """Build transit GeoJSON for a metro. Returns counts dict."""
    web_dir = settings.web_data_dir(metro.metro_id)
    routes_gz = web_dir / "transit_routes.geojson.gz"
    stops_gz = web_dir / "transit_stops.geojson.gz"

    if routes_gz.exists() and stops_gz.exists() and not force:
        logger.info("Transit GeoJSON exists, skipping: %s", web_dir)
        return {"routes": 0, "stops": 0, "skipped": True}

    # Import all the helpers from the script — they stay in the script file
    # until a future cleanup moves them here
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))
    from build_transit_geojson import (
        _load_feed_manifest,
        _load_trips_from_zips,
        _load_stop_modes,
        _stops_for_routes,
        build_routes_geojson,
        build_stops_geojson,
    )

    from urbanstack.extract.gtfs import extract_gtfs

    result = extract_gtfs(settings, metro, force=force)
    all_routes = result["routes"]
    all_stops = result["stops"]
    all_shapes = result["shapes"]

    if all_routes.is_empty():
        logger.warning("No GTFS routes for %s — writing empty transit GeoJSON", metro.metro_id)
        empty = {"type": "FeatureCollection", "features": []}
        web_dir.mkdir(parents=True, exist_ok=True)
        for path in (web_dir / "transit_routes.geojson", web_dir / "transit_stops.geojson"):
            path.write_text(json.dumps(empty))
            gz_path = Path(str(path) + ".gz")
            gz_path.write_bytes(gzip.compress(path.read_bytes()))
        return {"routes": 0, "stops": 0}

    agencies = all_routes["agency"].unique().to_list()
    raw_dir = settings.metro_raw_dir(metro.metro_id) / "gtfs"
    trips_df = _load_trips_from_zips(raw_dir, agencies)

    active_stops, stop_modes = _load_stop_modes(raw_dir, agencies)

    pad = 0.3
    clip = (metro.bounds[0] - pad, metro.bounds[1] + pad, metro.bounds[2] - pad, metro.bounds[3] + pad)

    routes_geojson = build_routes_geojson(all_shapes, all_routes, trips_df, clip_bounds=clip)
    route_count = len(routes_geojson["features"])

    rendered_routes: set[tuple[str, str]] = set()
    for feat in routes_geojson["features"]:
        p = feat["properties"]
        rendered_routes.add((p["agency"], p.get("route_id", "")))

    import polars as pl

    rendered_stop_keys = _stops_for_routes(raw_dir, agencies, rendered_routes) if rendered_routes else set()
    all_stops = all_stops.filter(
        (pl.col("latitude") >= clip[0]) & (pl.col("latitude") <= clip[1])
        & (pl.col("longitude") >= clip[2]) & (pl.col("longitude") <= clip[3])
    )
    stops_geojson = build_stops_geojson(all_stops, rendered_stop_keys, stop_modes)
    stop_count = len(stops_geojson["features"])

    web_dir.mkdir(parents=True, exist_ok=True)
    for name, geojson in [("transit_routes", routes_geojson), ("transit_stops", stops_geojson)]:
        path = web_dir / f"{name}.geojson"
        path.write_text(json.dumps(geojson))
        gz_path = Path(str(path) + ".gz")
        gz_path.write_bytes(gzip.compress(path.read_bytes()))
        logger.info("Wrote %s (%.0f KB)", gz_path, gz_path.stat().st_size / 1024)

    return {"routes": route_count, "stops": stop_count}
```

Note: This imports helper functions from the existing script to avoid duplicating 400 lines. A future cleanup task can move those helpers into this module.

- [ ] **Step 2: Update the old script to be a thin wrapper**

Replace the `main()` function body in `scripts/build_transit_geojson.py` with:

```python
def main() -> int:
    import argparse as ap
    from urbanstack.config import load_settings
    from urbanstack.metro import get_metro
    from urbanstack.transit_geojson import build_transit_geojson

    parser = ap.ArgumentParser(description="Build transit GeoJSON (deprecated — use: urbanstack transit-geojson)")
    parser.add_argument("--metro", default="dfw")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    settings = load_settings()
    settings.ensure_dirs()
    metro = get_metro(args.metro)
    result = build_transit_geojson(settings, metro, force=args.force)
    logger.info("Routes: %d, Stops: %d", result.get("routes", 0), result.get("stops", 0))
    return 0
```

- [ ] **Step 3: Verify the module imports correctly**

Run: `cd pipeline && uv run python -c "from urbanstack.transit_geojson import build_transit_geojson; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add pipeline/src/urbanstack/transit_geojson.py pipeline/scripts/build_transit_geojson.py
git commit -m "feat: extract transit GeoJSON builder into importable module"
```

---

### Task 5: Wire new commands into CLI

**Files:**
- Modify: `pipeline/src/urbanstack/cli.py`

- [ ] **Step 1: Add `sync-web`, `validate`, `transit-geojson`, and `pipeline` commands**

Add these command handler functions to `cli.py`:

```python
def cmd_sync_web(_args: argparse.Namespace, settings: Settings) -> None:
    from urbanstack.sync_web import sync_web

    web_root = Path(settings.data_dir).resolve().parent.parent / "web"
    sync_web(web_root)


def cmd_validate(args: argparse.Namespace, settings: Settings) -> None:
    from urbanstack.validate import format_report, validate_metro

    web_ts = Path(settings.data_dir).resolve().parent.parent / "web" / "src" / "lib" / "metro.ts"
    metros = list(METRO_REGISTRY.values()) if args.metro == "all" else [get_metro(args.metro)]
    all_ok = True
    for metro in metros:
        report = validate_metro(metro, settings, web_ts_path=web_ts)
        print(format_report(report))
        print()
        if not report.ok:
            all_ok = False
    if not all_ok:
        raise SystemExit(1)


def cmd_transit_geojson(args: argparse.Namespace, settings: Settings) -> None:
    from urbanstack.transit_geojson import build_transit_geojson

    metros = list(METRO_REGISTRY.values()) if args.metro == "all" else [get_metro(args.metro)]
    for metro in metros:
        logger.info("Building transit GeoJSON for %s", metro.metro_id)
        result = build_transit_geojson(settings, metro, force=args.force)
        logger.info("  Routes: %d, Stops: %d", result.get("routes", 0), result.get("stops", 0))


def cmd_pipeline(args: argparse.Namespace, settings: Settings) -> None:
    metros = list(METRO_REGISTRY.values()) if args.metro == "all" else [get_metro(args.metro)]

    for metro in metros:
        logger.info("━━━ Pipeline: %s ━━━", metro.metro_name)

        # 1. Extract
        logger.info("Step 1/6: Extract")
        for source in EXTRACTORS:
            try:
                _run_extractor(source, settings, metro, args.year, force=args.force)
            except Exception as exc:
                logger.warning("Extract %s failed (continuing): %s", source, exc)

        # 2. Transform
        logger.info("Step 2/6: Transform")
        from urbanstack.transform.block_group_mart import build_block_group_mart
        from urbanstack.transform.county_mart import build_county_mart, build_year_overlays
        from urbanstack.transform.metro_mart import build_metro_mart

        build_county_mart(settings, metro, force=args.force)
        build_block_group_mart(settings, metro, force=args.force)
        build_metro_mart(settings, metro, force=args.force)
        build_year_overlays(settings, metro)

        # 3. Transit GeoJSON
        logger.info("Step 3/6: Transit GeoJSON")
        try:
            from urbanstack.transit_geojson import build_transit_geojson
            build_transit_geojson(settings, metro, force=args.force)
        except Exception as exc:
            logger.warning("Transit GeoJSON failed (continuing): %s", exc)

        # 4. Export PMTiles
        logger.info("Step 4/6: Export PMTiles")
        try:
            _export_single_metro(metro.metro_id, settings)
        except Exception as exc:
            logger.warning("PMTiles export failed (continuing): %s", exc)

    # 5. Sync web (once, not per-metro)
    logger.info("Step 5/6: Sync metro.ts")
    from urbanstack.sync_web import sync_web
    web_root = Path(settings.data_dir).resolve().parent.parent / "web"
    sync_web(web_root)

    # 6. Validate
    logger.info("Step 6/6: Validate")
    from urbanstack.validate import format_report, validate_metro
    web_ts = web_root / "src" / "lib" / "metro.ts"
    for metro in metros:
        report = validate_metro(metro, settings, web_ts_path=web_ts)
        print(format_report(report))
        print()
```

Add the `Path` import at the top of `cli.py`:

```python
from pathlib import Path
```

Register the new subcommands in `main()`, after the existing subcommand registrations and before `args = parser.parse_args()`:

```python
    # transit-geojson
    p_transit = sub.add_parser("transit-geojson", help="Build transit route/stop GeoJSON")
    p_transit.add_argument("--metro", required=True, choices=["all", *metro_choices])
    p_transit.add_argument("--force", action="store_true")

    # sync-web
    sub.add_parser("sync-web", help="Generate web/src/lib/metro.ts from Python registry")

    # validate
    p_validate = sub.add_parser("validate", help="Validate metro data completeness")
    p_validate.add_argument("--metro", required=True, choices=["all", *metro_choices])

    # pipeline
    p_pipeline = sub.add_parser("pipeline", help="Run full pipeline: extract → transform → transit → export → sync → validate")
    p_pipeline.add_argument("--metro", required=True, choices=["all", *metro_choices])
    p_pipeline.add_argument("--year", type=int, default=None)
    p_pipeline.add_argument("--force", action="store_true")
```

Add the new commands to the `commands` dict in `main()`:

```python
    commands = {
        "extract": cmd_extract,
        "transform": cmd_transform,
        "export": cmd_export,
        "extract-national": cmd_extract_national,
        "national": cmd_national,
        "load": cmd_load,
        "transit-geojson": cmd_transit_geojson,
        "sync-web": cmd_sync_web,
        "validate": cmd_validate,
        "pipeline": cmd_pipeline,
    }
```

- [ ] **Step 2: Verify CLI help shows new commands**

Run: `cd pipeline && uv run python -m urbanstack.cli --help`
Expected: Output includes `pipeline`, `transit-geojson`, `sync-web`, `validate`

- [ ] **Step 3: Test `sync-web` command end-to-end**

Run: `cd pipeline && uv run python -m urbanstack.cli sync-web`
Expected: Writes `web/src/lib/metro.ts` with AUTO-GENERATED header

- [ ] **Step 4: Test `validate` command**

Run: `cd pipeline && uv run python -m urbanstack.cli validate --metro denver`
Expected: Prints validation report for Denver with source/mart/file checks

- [ ] **Step 5: Run full test suite**

Run: `cd pipeline && uv run pytest tests/ -v`
Expected: All tests PASS (existing + new)

- [ ] **Step 6: Commit**

```bash
git add pipeline/src/urbanstack/cli.py
git commit -m "feat: add pipeline, transit-geojson, sync-web, validate CLI commands"
```

---

### Task 6: End-to-end verification

**Files:** None (verification only)

- [ ] **Step 1: Run sync-web and verify metro.ts matches expected output**

Run: `cd pipeline && uv run python -m urbanstack.cli sync-web`

Then verify `web/src/lib/metro.ts`:
- Has AUTO-GENERATED header
- Contains all 9 metros sorted alphabetically
- Contains 4 regions with correct metro_ids
- Has METRO_TO_REGION lookup

- [ ] **Step 2: Run validate for all metros**

Run: `cd pipeline && uv run python -m urbanstack.cli validate --metro all`
Expected: Reports for all 9 metros, all critical checks pass

- [ ] **Step 3: Verify the dev server still works**

Ask user to run: `! cd web && npm run dev`
Open app, verify metros load, block groups work, regions work.

- [ ] **Step 4: Run full test suite one final time**

Run: `cd pipeline && uv run pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 5: Final commit with any remaining changes**

```bash
git add -A
git commit -m "feat: pipeline automation — single command for end-to-end metro setup"
```
