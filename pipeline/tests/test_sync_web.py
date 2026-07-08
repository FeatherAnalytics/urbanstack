import re

from urbanstack.sync_web import generate_metro_ts


def test_generate_metro_ts_has_header() -> None:
    ts = generate_metro_ts()
    assert "AUTO-GENERATED" in ts
    assert "do not edit manually" in ts


def test_generate_metro_ts_has_metros() -> None:
    ts = generate_metro_ts()
    assert "export const METROS" in ts
    assert "dfw:" in ts
    assert "cheyenne:" in ts


def test_generate_metro_ts_has_regions() -> None:
    ts = generate_metro_ts()
    assert "export const REGIONS" in ts
    assert "texas:" in ts
    assert "mountain:" in ts


def test_generate_metro_ts_has_metro_to_region() -> None:
    ts = generate_metro_ts()
    assert "METRO_TO_REGION" in ts


def test_generate_metro_ts_metros_sorted_alphabetically() -> None:
    ts = generate_metro_ts()
    # Extract keys from the METROS block — lines like "  austin: {"
    metros_match = re.search(
        r"export const METROS.*?=.*?\{(.*?)\n\};",
        ts,
        re.DOTALL,
    )
    assert metros_match, "Could not find METROS block"
    body = metros_match.group(1)
    keys = re.findall(r"^\s+(\w+):\s*\{", body, re.MULTILINE)
    assert keys == sorted(keys), f"METROS keys not sorted: {keys}"
    assert len(keys) > 1, "Expected multiple metro keys"


def test_generate_metro_ts_valid_typescript_syntax() -> None:
    ts = generate_metro_ts()
    assert ts.count("export interface MetroConfig") == 1
    assert ts.count("export interface RegionConfig") == 1
    assert ts.count("export const METROS") == 1
    assert ts.count("export const REGIONS") == 1
    assert ts.count("export const METRO_TO_REGION") == 1
