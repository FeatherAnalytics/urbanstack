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

EXTRACTORS: dict[str, str] = {
    "acs": "acs",
    "fars": "fars",
    "ntd": "ntd",
    "umr": "umr",
    "fhwa": "fhwa",
    "epa_sld": "epa_sld",
    "gtfs": "gtfs",
    "gazetteer": "gazetteer",
    "usaspending": "usaspending",
    "tmas_stations": "tmas_stations",
}


def _run_extractor(
    name: str,
    settings: Settings,
    metro: MetroConfig,
    year: int | None,
    *,
    force: bool,
) -> None:
    if name == "acs":
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
    else:
        raise ValueError(f"Unknown extractor: {name}")


def cmd_extract(args: argparse.Namespace, settings: Settings) -> None:
    metro = get_metro(args.metro)
    sources = list(EXTRACTORS) if args.source == "all" else [args.source]
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


def cmd_export(args: argparse.Namespace, settings: Settings) -> None:
    import subprocess
    import sys

    metro = get_metro(args.metro)
    web_dir = settings.web_data_dir(metro.metro_id)
    geojson_path = web_dir / "block_groups.geojson"
    if not geojson_path.exists():
        logger.error("GeoJSON not found: %s", geojson_path)
        sys.exit(1)

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
            "-o",
            str(output_path),
            "-l",
            "block_groups",
            str(geojson_path),
        ],
        check=True,
    )
    logger.info("PMTiles written: %s (%.1f MB)", output_path, output_path.stat().st_size / 1e6)


def cmd_national(args: argparse.Namespace, settings: Settings) -> None:
    from urbanstack.transform.block_group_mart import build_national_block_group_mart

    logger.info("Building national block group mart")
    build_national_block_group_mart(settings, force=args.force)


def cmd_extract_national(args: argparse.Namespace, settings: Settings) -> None:
    from urbanstack.extract.acs import extract_acs_national

    year = args.year or 2023
    for granularity in ["county", "block_group"]:
        logger.info("Extracting national ACS %s for %d", granularity, year)
        extract_acs_national(settings, granularity=granularity, year=year, force=args.force)


def cmd_load(_args: argparse.Namespace, _settings: Settings) -> None:
    logger.info("DuckDB load not yet implemented")


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
    p_export.add_argument("--metro", required=True, choices=metro_choices)

    # extract-national
    p_extract_nat = sub.add_parser("extract-national", help="Extract national ACS data")
    p_extract_nat.add_argument("--year", type=int, default=None)
    p_extract_nat.add_argument("--force", action="store_true")

    # national
    p_national = sub.add_parser("national", help="Build national block group mart")
    p_national.add_argument("--force", action="store_true")

    # load
    sub.add_parser("load", help="Load marts into DuckDB")

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = load_settings()
    settings.ensure_dirs()

    commands = {
        "extract": cmd_extract,
        "transform": cmd_transform,
        "export": cmd_export,
        "extract-national": cmd_extract_national,
        "national": cmd_national,
        "load": cmd_load,
    }
    commands[args.command](args, settings)


if __name__ == "__main__":
    main()
