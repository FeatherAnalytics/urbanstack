# Comprehensive Transit Data Coverage — Design Spec

**Date:** 2026-06-26
**Status:** Approved

## Problem

NYC metro config has only 1 GTFS feed (MTA subway) despite 10+ transit agencies
serving the MSA. Result: 13K stops vs Chicago's 226K — NYC should far exceed
Chicago. DFW and Chicago appear complete but haven't been validated against an
authoritative catalog.

Hardcoded `gtfs_feeds` in `MetroConfig` creates a maintenance burden and makes
it easy to miss agencies when adding new metros.

## Solution

Replace hardcoded GTFS feed URLs with auto-discovery from the Mobility Database
CSV catalog. Discovery uses metro bounding box to find all active GTFS feeds
overlapping the metro area.

## Design

### Transit Discovery Module

**New file:** `pipeline/src/urbanstack/extract/transit_discovery.py`

Downloads the Mobility Database CSV catalog (`files.mobilitydatabase.org/feeds_v2.csv`,
~2.4MB, free, no auth, updated daily). Filters to active GTFS feeds overlapping
a metro's bounding box.

**Type:**

```python
@dataclass(frozen=True)
class DiscoveredFeed:
    mdb_id: str           # e.g. "mdb-152"
    provider: str         # e.g. "Dallas Area Rapid Transit"
    download_url: str     # direct GTFS zip URL
    stable_url: str       # MobilityData-hosted stable URL (fallback)
    municipality: str
    subdivision: str
```

**Filtering pipeline:**
1. `data_type == "gtfs"` (exclude GTFS-RT)
2. `status == "active"` (exclude deprecated/inactive)
3. Feed bounding box overlaps metro bounding box
4. `urls.authentication_type == 0` (no auth required)

**Caching:** CSV cached locally. Skip re-download if file exists and < 24h old.

**Function signature:**

```python
def discover_feeds(settings: Settings, metro: MetroConfig) -> list[DiscoveredFeed]:
```

### MetroConfig Changes

**Remove:** `gtfs_feeds` field (replaced by discovery).

**Keep:** `transit_agencies` field (NTD IDs — separate concern, rarely changes,
FTA crosswalk join too fuzzy for auto-discovery).

**Add:** `bounds` field for geographic filtering.

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
    umr_names: list[str] = field(default_factory=list)
```

**Bounds values:**
- DFW: `(32.25, 33.45, -97.60, -96.00)`
- Chicago: `(40.80, 42.50, -88.70, -87.20)`
- NYC: `(40.10, 41.60, -74.90, -73.30)`

### GTFS Extract Module Changes

`extract_gtfs()` calls `discover_feeds()` instead of reading `metro.gtfs_feeds`.

**New data flow:**

```
extract_gtfs(settings, metro)
  → discover_feeds(settings, metro)    # list[DiscoveredFeed]
  → _download_feed() per feed          # existing download logic
  → _parse_routes/stops/shapes()       # existing parse logic, unchanged
  → write parquet                      # existing output, unchanged
```

**Changes to `extract/gtfs.py`:**
- Replace `metro.gtfs_feeds` lookup with `discover_feeds()` call
- Agency name from `DiscoveredFeed.provider`
- Download tries `download_url` first, falls back to `stable_url`
- Remove `agencies` parameter (no longer selecting from hardcoded list)
- Existing error handling (`try/except` on download failures) unchanged

### Downstream Impact

**Unchanged:**
- GTFS contracts (`GtfsRoute`, `GtfsStop`, `GtfsShape`)
- Parquet output format
- Transit GeoJSON builder
- Frontend `TransitLayer.tsx`
- NTD extract (still uses `metro.transit_agencies`)
- All transform/mart logic

**Expected feed counts:**
- DFW: 3-4 feeds (DART, Trinity Metro, DCTA, possibly STAR Transit)
- Chicago: 3-5 feeds (CTA, Metra, Pace, possibly South Shore Line)
- NYC: 10-15 feeds (MTA subway, MTA bus, LIRR, Metro-North, NJ Transit bus,
  NJ Transit rail, PATH, NY Waterway, Suffolk Transit, etc.)

**Data volume:** NYC stops grow from ~13K to potentially 100K+. All local
parquet/GeoJSON — no backend changes needed.

## Success Criteria

- [ ] Discovery module finds all active GTFS feeds per metro by bounding box
- [ ] MetroConfig no longer has `gtfs_feeds` field
- [ ] MetroConfig has `bounds` field for all 3 metros
- [ ] GTFS extract uses discovery instead of hardcoded feed list
- [ ] NYC GTFS data includes NJ Transit, PATH, MTA Bus, LIRR, Metro-North
- [ ] DFW and Chicago feed counts validated against catalog (no regressions)
- [ ] Existing tests updated and passing
- [ ] Pipeline runs successfully for all 3 metros

## Out of Scope

- NTD ID auto-discovery (keep manual in MetroConfig)
- Mobility Database API integration (CSV sufficient)
- GTFS-RT feeds (real-time data)
- New metro additions (this is about coverage for existing 3)
- Frontend changes (none needed)
