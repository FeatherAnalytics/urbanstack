"""Metro data completeness validation.

Checks staging sources, mart outputs, web assets, and null columns
to produce a per-metro health report.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import polars as pl

if TYPE_CHECKING:
    from pathlib import Path

    from urbanstack.config import Settings
    from urbanstack.metro import MetroConfig

logger = logging.getLogger("urbanstack.validate")

# (source_name, glob for county-level file, optional block-group glob)
STAGING_SOURCES: list[tuple[str, str, str | None]] = [
    ("acs", "acs/acs_county_*.parquet", "acs/acs_block_group_*.parquet"),
    ("epa_sld", "epa_sld/epa_sld_*.parquet", None),
    ("fars", "fars/fars_*_*.parquet", None),
    ("fhwa", "fhwa/fhwa_*.parquet", None),
    ("gazetteer", "gazetteer/gazetteer_*.parquet", None),
    ("gtfs", "gtfs/gtfs_stops.parquet", None),
    ("ntd", "ntd/ntd_*.parquet", None),
    ("osm_parks", "osm_parks/osm_parks_*.parquet", None),
    ("tmas_stations", "tmas_stations/tmas_stations_*.parquet", None),
    ("umr", "umr/umr_*.parquet", None),
    ("usaspending", "usaspending/usaspending_*.parquet", None),
]

OPTIONAL_SOURCES: set[str] = {"umr"}

MART_FILES: list[str] = [
    "county_summary.parquet",
    "block_group_summary.parquet",
    "metro_summary.parquet",
]


@dataclass
class FileCheck:
    """Result of checking a single file."""

    exists: bool
    size_bytes: int = 0
    row_count: int = 0


@dataclass
class MetroReport:
    """Completeness report for a single metro area."""

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
        logger.warning("%s: %s", self.metro_id, msg)

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)
        logger.error("%s: %s", self.metro_id, msg)


def check_file(path: Path) -> FileCheck:
    """Check whether a file exists and its size."""
    if not path.exists():
        return FileCheck(exists=False)
    return FileCheck(exists=True, size_bytes=path.stat().st_size)


def check_parquet(path: Path) -> FileCheck:
    """Check a Parquet file for existence and row count."""
    if not path.exists():
        return FileCheck(exists=False, row_count=0)
    try:
        row_count = pl.scan_parquet(path).select(pl.len()).collect().item()
        return FileCheck(
            exists=True,
            size_bytes=path.stat().st_size,
            row_count=row_count,
        )
    except Exception:
        logger.exception("Failed to read parquet: %s", path)
        return FileCheck(exists=True, size_bytes=path.stat().st_size, row_count=0)


def _find_null_columns(parquet_path: Path) -> list[str]:
    """Find columns where every value is null in a Parquet file."""
    if not parquet_path.exists():
        return []
    try:
        df = pl.read_parquet(parquet_path)
        return [col for col in df.columns if df[col].is_null().all()]
    except Exception:
        logger.exception("Failed to scan nulls: %s", parquet_path)
        return []


def _check_metro_ts_sync(metro: MetroConfig, web_ts_path: Path | None) -> str | None:
    """Check if metro.ts includes this metro. Returns error string or None."""
    if web_ts_path is None or not web_ts_path.exists():
        return None
    content = web_ts_path.read_text()
    if f"{metro.metro_id}:" not in content:
        return f"{metro.metro_id} not found in {web_ts_path.name}"
    return None


def validate_metro(
    metro: MetroConfig,
    settings: Settings,
    *,
    web_ts_path: Path | None = None,
) -> MetroReport:
    """Run all validation checks for a metro area."""
    report = MetroReport(metro_id=metro.metro_id, metro_name=metro.metro_name)
    staging = settings.metro_staging_dir(metro.metro_id)
    marts = settings.metro_marts_dir(metro.metro_id)
    web_dir = settings.web_data_dir(metro.metro_id)

    # --- Staging sources ---
    for name, glob_pattern, bg_pattern in STAGING_SOURCES:
        matches = list(staging.glob(glob_pattern))
        if matches:
            fc = check_parquet(matches[0])
            report.sources[name] = fc
        else:
            report.sources[name] = FileCheck(exists=False)
            msg = f"Staging source missing: {name} ({glob_pattern})"
            if name in OPTIONAL_SOURCES:
                report.add_warning(msg)
            else:
                report.add_error(msg)

        if bg_pattern:
            bg_matches = list(staging.glob(bg_pattern))
            bg_key = f"{name}_bg"
            if bg_matches:
                report.sources[bg_key] = check_parquet(bg_matches[0])
            else:
                report.sources[bg_key] = FileCheck(exists=False)
                report.add_error(f"Staging source missing: {bg_key} ({bg_pattern})")

    # --- Mart outputs ---
    for mart_file in MART_FILES:
        path = marts / mart_file
        fc = check_parquet(path)
        report.marts[mart_file] = fc
        if not fc.exists:
            report.add_error(f"Mart missing: {mart_file}")

    # --- Web assets: boundaries (required) ---
    for geojson_name in ("counties.geojson", "block_groups.geojson"):
        path = web_dir / geojson_name
        fc = check_file(path)
        report.files[geojson_name] = fc
        if not fc.exists:
            report.add_error(f"Boundary GeoJSON missing: {geojson_name}")

    # --- Web assets: transit (warning only) ---
    for transit_name in ("transit_routes.geojson", "transit_stops.geojson"):
        path = web_dir / transit_name
        fc = check_file(path)
        report.files[transit_name] = fc
        if not fc.exists:
            report.add_warning(f"Transit GeoJSON missing: {transit_name}")

    # --- Web assets: PMTiles (warning only) ---
    pmtiles_path = settings.exports_dir / f"{metro.metro_id}_block_groups.pmtiles"
    fc = check_file(pmtiles_path)
    report.files["pmtiles"] = fc
    if not fc.exists:
        report.add_warning(f"PMTiles missing: {pmtiles_path.name}")

    # --- Null columns in county_summary ---
    county_parquet = marts / "county_summary.parquet"
    report.null_columns = _find_null_columns(county_parquet)
    for col in report.null_columns:
        report.add_warning(f"All-null column in county_summary: {col}")

    # --- metro.ts sync check ---
    sync_err = _check_metro_ts_sync(metro, web_ts_path)
    if sync_err:
        report.add_warning(sync_err)

    return report


def format_report(report: MetroReport) -> str:
    """Format a MetroReport as a human-readable string."""
    lines: list[str] = []
    status = "OK" if report.ok else "FAIL"
    lines.append(f"=== {report.metro_name} ({report.metro_id}) — {status} ===")
    lines.append("")

    # Sources
    lines.append("Staging Sources:")
    for name, fc in sorted(report.sources.items()):
        mark = "+" if fc.exists else "-"
        detail = f"{fc.row_count:,} rows" if fc.exists and fc.row_count else ""
        lines.append(f"  [{mark}] {name}  {detail}".rstrip())

    lines.append("")
    lines.append("Marts:")
    for name, fc in sorted(report.marts.items()):
        mark = "+" if fc.exists else "-"
        detail = f"{fc.row_count:,} rows" if fc.exists and fc.row_count else ""
        lines.append(f"  [{mark}] {name}  {detail}".rstrip())

    lines.append("")
    lines.append("Web Assets:")
    for name, fc in sorted(report.files.items()):
        mark = "+" if fc.exists else "-"
        size_mb = f"{fc.size_bytes / 1_000_000:.1f} MB" if fc.exists else ""
        lines.append(f"  [{mark}] {name}  {size_mb}".rstrip())

    if report.null_columns:
        lines.append("")
        lines.append("Null Columns (county_summary):")
        for col in report.null_columns:
            lines.append(f"  - {col}")

    if report.warnings:
        lines.append("")
        lines.append(f"Warnings ({len(report.warnings)}):")
        for w in report.warnings:
            lines.append(f"  ! {w}")

    if report.errors:
        lines.append("")
        lines.append(f"Errors ({len(report.errors)}):")
        for e in report.errors:
            lines.append(f"  X {e}")

    lines.append("")
    return "\n".join(lines)
