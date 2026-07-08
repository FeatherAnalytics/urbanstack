"""UrbanStack data pipeline CLI."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from urbanstack.config import Settings, load_settings
from urbanstack.metro import METRO_REGISTRY, get_metro

if TYPE_CHECKING:
    from urbanstack.metro import MetroConfig

logger = logging.getLogger("urbanstack.cli")


def _setup_ssl() -> None:
    """Inject OS trust store if default certs fail."""
    import requests

    try:
        requests.head("https://data.transportation.gov", timeout=5)
    except requests.exceptions.SSLError:
        import truststore

        truststore.inject_into_ssl()
        logger.info("Injected OS trust store for SSL")

EXTRACTORS: list[str] = [
    "boundaries",
    "acs",
    "fars",
    "ntd",
    "umr",
    "fhwa",
    "epa_sld",
    "gtfs",
    "gazetteer",
    "usaspending",
    "tmas_stations",
    "osm_parks",
]


def _resolve_metros(metro_arg: str) -> list[MetroConfig]:
    """Resolve 'all' or a single metro ID to a list of MetroConfig."""
    if metro_arg == "all":
        return list(METRO_REGISTRY.values())
    return [get_metro(metro_arg)]


def _web_root(settings: Settings) -> Path:
    """Resolve the web/ directory from settings.data_dir."""
    return Path(settings.data_dir).resolve().parent.parent / "web"


def _run_extractor(
    name: str,
    settings: Settings,
    metro: MetroConfig,
    year: int | None,
    *,
    force: bool,
) -> None:
    if name == "boundaries":
        from urbanstack.extract.boundaries import extract_boundaries

        extract_boundaries(settings, metro, force=force)
    elif name == "acs":
        from urbanstack.extract.acs import extract_acs

        extract_acs(settings, metro, granularity="county", year=year or 2023, force=force)
        extract_acs(settings, metro, granularity="block_group", year=year or 2023, force=force)
    elif name == "fars":
        from urbanstack.extract.fars import extract_fars

        extract_fars(settings, metro, force=force)
    elif name == "ntd":
        from urbanstack.extract.ntd import extract_ntd

        extract_ntd(settings, metro, force=force)
    elif name == "umr":
        from urbanstack.extract.umr import extract_umr

        extract_umr(settings, metro, force=force)
    elif name == "fhwa":
        from urbanstack.extract.fhwa import extract_fhwa

        extract_fhwa(settings, metro, year=year or 2023, force=force)
    elif name == "epa_sld":
        from urbanstack.extract.epa_sld import extract_epa_sld

        extract_epa_sld(settings, metro, force=force)
    elif name == "gtfs":
        from urbanstack.extract.gtfs import extract_gtfs

        extract_gtfs(settings, metro, force=force)
    elif name == "gazetteer":
        from urbanstack.extract.gazetteer import extract_gazetteer

        extract_gazetteer(settings, metro, force=force)
    elif name == "usaspending":
        from urbanstack.extract.usaspending import extract_usaspending

        extract_usaspending(settings, metro, force=force)
    elif name == "tmas_stations":
        from urbanstack.extract.tmas_stations import extract_tmas_stations

        extract_tmas_stations(settings, metro, force=force)
    elif name == "osm_parks":
        from urbanstack.extract.osm_parks import extract_osm_parks

        extract_osm_parks(settings, metro, force=force)
    else:
        raise ValueError(f"Unknown extractor: {name}")


def cmd_extract(args: argparse.Namespace, settings: Settings) -> None:
    metro = get_metro(args.metro)
    sources = EXTRACTORS if args.source == "all" else [args.source]
    for source in sources:
        logger.info("Extracting %s for %s", source, metro.metro_id)
        _run_extractor(source, settings, metro, args.year, force=args.force)


def cmd_transform(args: argparse.Namespace, settings: Settings) -> None:
    metro = get_metro(args.metro)

    from urbanstack.transform.block_group_mart import build_block_group_mart
    from urbanstack.transform.county_mart import build_county_mart, build_year_overlays
    from urbanstack.transform.metro_mart import build_metro_mart

    logger.info("Building county mart for %s", metro.metro_id)
    build_county_mart(settings, metro, force=args.force)

    logger.info("Building block group mart for %s", metro.metro_id)
    build_block_group_mart(settings, metro, force=args.force)

    logger.info("Building metro mart for %s", metro.metro_id)
    build_metro_mart(settings, metro, force=args.force)

    logger.info("Building year overlays for %s", metro.metro_id)
    build_year_overlays(settings, metro)


def _export_single_metro(metro_id: str, settings: Settings) -> None:
    import subprocess

    metro = get_metro(metro_id)
    web_dir = settings.web_data_dir(metro.metro_id)
    geojson_path = web_dir / "block_groups.geojson"
    if not geojson_path.exists():
        logger.warning("GeoJSON not found, skipping %s: %s", metro.metro_id, geojson_path)
        return

    settings.exports_dir.mkdir(parents=True, exist_ok=True)
    output_path = settings.exports_dir / f"{metro.metro_id}_block_groups.pmtiles"

    # yagni: inline tippecanoe call, extract to module when there are 3+ export formats
    logger.info("Building PMTiles for %s: %s → %s", metro.metro_id, geojson_path, output_path)
    subprocess.run(
        [
            "tippecanoe",
            "-ab",
            "-z12",
            "-Z3",
            "--coalesce-densest-as-needed",
            "--force",
            "--buffer=127",
            "-o",
            str(output_path),
            "-l",
            "block_groups",
            str(geojson_path),
        ],
        check=True,
    )
    logger.info("PMTiles written: %s (%.1f MB)", output_path, output_path.stat().st_size / 1e6)


def cmd_export(args: argparse.Namespace, settings: Settings) -> None:
    if args.metro == "all":
        for metro_id in METRO_REGISTRY:
            _export_single_metro(metro_id, settings)
    else:
        _export_single_metro(args.metro, settings)


def cmd_national(args: argparse.Namespace, settings: Settings) -> None:
    from urbanstack.transform.block_group_mart import build_national_block_group_mart

    logger.info("Building national block group mart")
    try:
        build_national_block_group_mart(settings, force=args.force)
    except FileNotFoundError as exc:
        logger.warning("Skipping national mart — %s", exc)


def cmd_extract_national(args: argparse.Namespace, settings: Settings) -> None:
    from urbanstack.extract.acs import extract_acs_national

    year = args.year or 2023
    for granularity in ["county", "block_group"]:
        logger.info("Extracting national ACS %s for %d", granularity, year)
        extract_acs_national(settings, granularity=granularity, year=year, force=args.force)


def cmd_load(_args: argparse.Namespace, _settings: Settings) -> None:
    logger.info("DuckDB load not yet implemented")


def cmd_transit_geojson(args: argparse.Namespace, settings: Settings) -> None:
    from urbanstack.transit_geojson import build_transit_geojson

    metros = _resolve_metros(args.metro)
    for metro in metros:
        logger.info("Building transit GeoJSON for %s", metro.metro_id)
        result = build_transit_geojson(settings, metro, force=args.force)
        logger.info("  Routes: %d, Stops: %d", result.get("routes", 0), result.get("stops", 0))


def cmd_sync_web(_args: argparse.Namespace, settings: Settings) -> None:
    from urbanstack.sync_web import sync_web

    sync_web(_web_root(settings))


def cmd_validate(args: argparse.Namespace, settings: Settings) -> None:
    from urbanstack.validate import format_report, validate_metro

    web_ts = _web_root(settings) / "src" / "lib" / "metro.ts"
    metros = _resolve_metros(args.metro)
    all_ok = True
    for metro in metros:
        report = validate_metro(metro, settings, web_ts_path=web_ts)
        print(format_report(report))
        print()
        if not report.ok:
            all_ok = False
    if not all_ok:
        raise SystemExit(1)


def cmd_pipeline(args: argparse.Namespace, settings: Settings) -> None:
    metros = _resolve_metros(args.metro)

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

        for step_name, step_fn in [
            ("county mart", lambda: build_county_mart(settings, metro, force=args.force)),
            ("block group mart", lambda: build_block_group_mart(settings, metro, force=args.force)),
            ("metro mart", lambda: build_metro_mart(settings, metro, force=args.force)),
            ("year overlays", lambda: build_year_overlays(settings, metro)),
        ]:
            try:
                step_fn()
            except Exception as exc:
                logger.warning("Transform %s failed (continuing): %s", step_name, exc)

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
    sync_web(_web_root(settings))

    # 6. Validate
    logger.info("Step 6/6: Validate")
    from urbanstack.validate import format_report, validate_metro
    web_ts = _web_root(settings) / "src" / "lib" / "metro.ts"
    for metro in metros:
        report = validate_metro(metro, settings, web_ts_path=web_ts)
        print(format_report(report))
        print()


def main() -> None:
    parser = argparse.ArgumentParser(prog="urbanstack", description="UrbanStack data pipeline")
    sub = parser.add_subparsers(dest="command", required=True)

    metro_choices = sorted(METRO_REGISTRY)
    source_choices = ["all", *sorted(EXTRACTORS)]

    # extract
    p_extract = sub.add_parser("extract", help="Extract raw data from sources")
    p_extract.add_argument("--metro", required=True, choices=metro_choices)
    p_extract.add_argument("--source", default="all", choices=source_choices)
    p_extract.add_argument("--year", type=int, default=None)
    p_extract.add_argument("--force", action="store_true")

    # transform
    p_transform = sub.add_parser("transform", help="Build mart summaries")
    p_transform.add_argument("--metro", required=True, choices=metro_choices)
    p_transform.add_argument("--force", action="store_true")

    # export
    p_export = sub.add_parser("export", help="Export PMTiles from GeoJSON")
    p_export.add_argument("--metro", required=True, choices=["all", *metro_choices])

    # extract-national
    p_extract_nat = sub.add_parser("extract-national", help="Extract national ACS data")
    p_extract_nat.add_argument("--year", type=int, default=None)
    p_extract_nat.add_argument("--force", action="store_true")

    # national
    p_national = sub.add_parser("national", help="Build national block group mart")
    p_national.add_argument("--force", action="store_true")

    # load
    sub.add_parser("load", help="Load marts into DuckDB")

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

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    _setup_ssl()
    settings = load_settings()
    settings.ensure_dirs()

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
    commands[args.command](args, settings)


if __name__ == "__main__":
    main()
