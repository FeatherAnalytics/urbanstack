import textwrap
from pathlib import Path
from unittest.mock import patch

from urbanstack.config import Settings
from urbanstack.extract.transit_discovery import DiscoveredFeed, discover_feeds
from urbanstack.metro import DFW

# ruff: noqa: E501
SAMPLE_CSV = textwrap.dedent("""\
    id,data_type,entity_type,location.country_code,location.subdivision_name,location.municipality,provider,is_official,name,note,feed_contact_email,static_reference,urls.direct_download,urls.authentication_type,urls.authentication_info,urls.api_key_parameter_name,urls.latest,urls.license,location.bounding_box.minimum_latitude,location.bounding_box.maximum_latitude,location.bounding_box.minimum_longitude,location.bounding_box.maximum_longitude,location.bounding_box.extracted_on,status,features,redirect.id,redirect.comment
    mdb-152,gtfs,,US,Texas,Dallas,Dallas Area Rapid Transit (DART),True,,,,,,0,,,,,32.65,33.10,-97.10,-96.50,2024-01-01,active,Shapes,,
    mdb-885,gtfs,,US,Texas,Fort Worth,Fort Worth Transit Authority (Trinity Metro),True,,,,,,0,,,,,32.60,32.95,-97.50,-97.10,2024-01-01,active,Shapes,,
    mdb-999,gtfs,,US,New York,New York,MTA New York City Transit,True,,,,,,0,,,,,40.50,40.92,-74.25,-73.70,2024-01-01,active,Shapes,,
    mdb-888,gtfs_rt,vp,US,Texas,Dallas,DART Realtime,True,,,,,,0,,,,,,,,2024-01-01,active,,,
    mdb-777,gtfs,,US,California,Los Angeles,LA Metro,True,,,,,,0,,,,,33.70,34.30,-118.70,-117.70,2024-01-01,active,Shapes,,
    mdb-666,gtfs,,US,Texas,Dallas,Inactive Feed,True,,,,,,0,,,,,32.70,32.90,-97.00,-96.70,2024-01-01,inactive,Shapes,,
    mdb-555,gtfs,,US,Texas,Dallas,Auth Required Feed,True,,,,,,1,,,,,32.70,32.90,-97.00,-96.70,2024-01-01,active,Shapes,,
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
    assert "LA Metro" not in provider_names
    assert "MTA New York City Transit" not in provider_names


def test_discover_feeds_excludes_gtfs_rt(settings: Settings) -> None:
    _write_catalog(settings)
    with patch("urbanstack.extract.transit_discovery._download_catalog") as mock_dl:
        mock_dl.return_value = settings.raw_dir / "catalog" / "feeds_v2.csv"
        feeds = discover_feeds(settings, DFW)

    ids = [f.mdb_id for f in feeds]
    assert "mdb-888" not in ids


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
