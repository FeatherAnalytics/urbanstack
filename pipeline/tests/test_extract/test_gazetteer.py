import io
import zipfile
from unittest.mock import MagicMock, patch

import polars as pl

from urbanstack.config import Settings
from urbanstack.contracts.gazetteer import GazetteerRecord
from urbanstack.extract.gazetteer import extract_gazetteer

HEADER = "USPS\tGEOID\tANSICODE\tNAME\tALAND\tAWATER\tALAND_SQMI\tAWATER_SQMI\tINTPTLAT\tINTPTLONG"

DALLAS_ROW = (
    "TX\t48113\t1383884\tDallas County"
    "\t2257107926\t42737429\t871.47\t16.50\t+32.7668236\t-96.7778539"
)
COLLIN_ROW = (
    "TX\t48085\t1383870\tCollin County"
    "\t2156817932\t60527039\t832.74\t23.37\t+33.1918596\t-96.5724085"
)
HARRIS_ROW = (
    "TX\t48201\t1383886\tHarris County"
    "\t4412070451\t98838558\t1703.50\t38.16\t+29.8574800\t-95.3931500"
)
LA_ROW = (
    "CA\t06037\t0277283\tLos Angeles County"
    "\t10510076640\t178768800\t4058.01\t69.02\t+34.3202960\t-118.2265750"
)


def _raw_text() -> str:
    return "\n".join([HEADER, DALLAS_ROW, COLLIN_ROW, HARRIS_ROW, LA_ROW]) + "\n"


def _make_zip_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("2024_Gaz_counties_national.txt", _raw_text())
    return buf.getvalue()


def test_filters_to_dfw(settings: Settings) -> None:
    mock_resp = MagicMock()
    mock_resp.content = _make_zip_bytes()
    mock_resp.raise_for_status = MagicMock()

    with patch("urbanstack.extract.gazetteer.requests.get", return_value=mock_resp):
        df = extract_gazetteer(settings, force=True)

    assert len(df) == 2
    fips = set(df["county_fips"].to_list())
    assert fips == {"48113", "48085"}
    assert "48201" not in fips
    assert "06037" not in fips


def test_contract_validation(settings: Settings) -> None:
    mock_resp = MagicMock()
    mock_resp.content = _make_zip_bytes()
    mock_resp.raise_for_status = MagicMock()

    with patch("urbanstack.extract.gazetteer.requests.get", return_value=mock_resp):
        df = extract_gazetteer(settings, force=True)

    row = df.filter(pl.col("county_fips") == "48113").to_dicts()[0]
    record = GazetteerRecord.model_validate(row)
    assert record.county_name == "Dallas County"
    assert record.state_abbr == "TX"
    assert record.land_area_sqm == 2257107926


def test_idempotent_skip(settings: Settings) -> None:
    parquet_dir = settings.staging_dir / "gazetteer"
    parquet_dir.mkdir(parents=True, exist_ok=True)
    parquet_path = parquet_dir / "gazetteer_dfw.parquet"
    existing = pl.DataFrame({"county_fips": ["48113"], "county_name": ["Dallas County"]})
    existing.write_parquet(parquet_path)

    with patch("urbanstack.extract.gazetteer.requests.get") as mock_get:
        df = extract_gazetteer(settings)
        mock_get.assert_not_called()

    assert len(df) == 1


def test_saves_raw_file(settings: Settings) -> None:
    mock_resp = MagicMock()
    mock_resp.content = _make_zip_bytes()
    mock_resp.raise_for_status = MagicMock()

    with patch("urbanstack.extract.gazetteer.requests.get", return_value=mock_resp):
        extract_gazetteer(settings, force=True)

    raw_path = settings.raw_dir / "gazetteer" / "2024_Gaz_counties_national.txt"
    assert raw_path.exists()
