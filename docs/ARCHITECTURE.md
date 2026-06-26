# UrbanStack Multi-Metro Architecture

Design document for scaling UrbanStack from a single-metro (DFW) platform to a multi-metro and eventually national urban data platform. This is a design document only — no code changes are included.

**Author:** UrbanStack Team  
**Date:** June 2026  
**Status:** Draft

---

## 1. Current Architecture

UrbanStack follows a four-stage pipeline:

```
Extract → Transform → Load → Web
```

**Extract** (`pipeline/src/urbanstack/extract/`): Ten extractors pull data from federal and local sources — Census ACS, NHTSA FARS, NTD, UMR, FHWA TMAS, EPA Smart Location Database, GTFS feeds, Census Gazetteer, USAspending, and TMAS station locations. Each produces validated Parquet files in `data/staging/`.

**Transform** (`pipeline/src/urbanstack/transform/`): Three mart builders (county, block group, metro) join staging tables, compute derived metrics, and write summary Parquet files to `data/marts/`. Two support modules — `spatial.py` (point-in-polygon joins) and `derived.py` (declarative metric registry) — are already geography-agnostic.

**Load** (`pipeline/src/urbanstack/load/`): `duckdb_loader.py` imports all mart Parquets into a local DuckDB database.

**Web** (`web/`): A Next.js app with deck.gl renders a choropleth map, metric selector, comparison chart, and county detail popup. Data is served as static JSON files in `web/public/data/`.

### What's Hardcoded to DFW

| File | Hardcoded Element |
|---|---|
| `geography.py` | `DFW_STATE_FIPS = "48"`, `DFW_COUNTY_FIPS` dict |
| All 10 extractors | Import from `geography.py`; DFW-specific agency IDs, URLs, metro names |
| `county_mart.py` | Filters by `DFW_STATE_FIPS` |
| `block_group_mart.py` | Filters by `DFW_STATE_FIPS`, references `dfw_block_groups.geojson` |
| `metro_mart.py` | `METRO_FIPS = "48DFW"`, `METRO_NAME = "Dallas-Fort Worth-Arlington MSA"` |
| `DFWMap.tsx` | Component name, `INITIAL_VIEW` (32.78, -96.85, zoom 8) |
| `data.ts` | File paths (`/data/county_summary.json`), no metro parameterization |
| `page.tsx` | "DFW Urban Data Explorer" title, `DFWMap` import |

### What's Already Generic

| File | Why It's Safe |
|---|---|
| All `contracts/*.py` | Pydantic models define schemas by shape, not by geography |
| `config.py` | `Settings` has `data_dir`, `census_api_key` — no metro coupling |
| `transform/spatial.py` | Point-in-polygon accepts any GeoJSON boundaries |
| `transform/derived.py` | Declarative metric registry, pure column math |
| `_socrata.py` | Generic pagination helper |
| `utils.py` | `find_parquet()` — directory-level utility |

---

## 2. Target Architecture

```
                     ┌──────────────┐
                     │ MetroConfig  │
                     │   Registry   │
                     └──────┬───────┘
                            │
              ┌─────────────┼──────────────┐
              ▼             ▼              ▼
        ┌──────────┐ ┌──────────┐  ┌──────────────┐
        │ Extract  │ │ Extract  │  │  Extract     │
        │  (DFW)   │ │(Chicago) │  │  (Houston)   │
        └────┬─────┘ └────┬─────┘  └──────┬───────┘
             │             │               │
             ▼             ▼               ▼
     data/staging/dfw  staging/chicago  staging/houston
             │             │               │
             ▼             ▼               ▼
        ┌──────────┐ ┌──────────┐  ┌──────────────┐
        │Transform │ │Transform │  │  Transform   │
        │  (DFW)   │ │(Chicago) │  │  (Houston)   │
        └────┬─────┘ └────┬─────┘  └──────┬───────┘
             │             │               │
             ▼             ▼               ▼
     data/marts/dfw   marts/chicago   marts/houston
             │             │               │
             └─────────────┼───────────────┘
                           ▼
                  ┌─────────────────┐
                  │ National Union  │
                  │  (DuckDB/API)   │
                  └────────┬────────┘
                           ▼
                  ┌─────────────────┐
                  │      Web        │
                  │  (metro picker) │
                  └─────────────────┘
```

Key principles:

1. **MetroConfig is the single source of geography.** No extractor, mart builder, or web component references a specific metro directly. All receive a `MetroConfig` object.
2. **Per-metro isolation at the data layer.** Each metro gets its own subdirectories under `raw/`, `staging/`, and `marts/`. Files are never mixed.
3. **National is a union, not a separate pipeline.** National tables are created by concatenating per-metro mart tables with a `metro_id` column.
4. **Web is metro-parameterized.** Data paths, viewport, and labels are driven by the selected metro's config.

---

## 3. MetroConfig Registry

Replace `geography.py` with a new module: `pipeline/src/urbanstack/metro.py`.

```python
from dataclasses import dataclass, field


@dataclass(frozen=True)
class MetroConfig:
    """All geography-specific parameters for a single metro area."""

    metro_id: str                        # "dfw", "chicago", "nyc"
    metro_name: str                      # "Dallas-Fort Worth-Arlington MSA"
    metro_fips: str                      # "19100" (CBSA code) or synthetic "48DFW"
    state_fips: str                      # "48" — primary state
    state_abbr: str                      # "TX"
    counties: dict[str, str]             # county name → 3-digit FIPS
    center: tuple[float, float]          # (lat, lon) for map viewport
    zoom: int                            # default zoom level
    bounds: tuple[float, float, float, float]  # (min_lat, max_lat, min_lon, max_lon)
    transit_agencies: dict[str, str]     # NTD ID → agency name
    # GTFS feeds auto-discovered via transit_discovery module (Mobility Database CSV catalog)
    umr_names: list[str]                 # metro name variations for UMR filtering

    @property
    def state_fips_int(self) -> int:
        return int(self.state_fips)

    @property
    def county_fips_set(self) -> set[str]:
        """Set of 3-digit county FIPS codes."""
        return set(self.counties.values())

    @property
    def county_fips_5_set(self) -> set[str]:
        """Set of 5-digit state+county FIPS codes."""
        return {f"{self.state_fips}{fips}" for fips in self.counties.values()}

    # Multi-state metros (e.g., NYC spans NY, NJ, CT) will need
    # additional_states: dict[str, dict[str, str]] added later.
    # yagni: single-state only until a multi-state metro is added.
```

### DFW Config

```python
DFW = MetroConfig(
    metro_id="dfw",
    metro_name="Dallas-Fort Worth-Arlington MSA",
    metro_fips="19100",
    state_fips="48",
    state_abbr="TX",
    counties={
        "Collin": "085",
        "Dallas": "113",
        "Denton": "121",
        "Ellis": "139",
        "Hood": "221",
        "Hunt": "231",
        "Johnson": "251",
        "Kaufman": "257",
        "Parker": "367",
        "Rockwall": "397",
        "Tarrant": "439",
        "Wise": "497",
    },
    center=(32.78, -96.85),
    zoom=8,
    transit_agencies={
        "60056": "Dallas Area Rapid Transit",
        "60007": "Fort Worth Transportation Authority",
        "60101": "Denton County Transportation Authority",
    },
    gtfs_feeds={
        "DART": "https://www.dart.org/transitdata/latest/google_transit.zip",
        "Trinity Metro": "http://sched.ridetm.org/gtfs/fwtatransitdata.zip",
        "DCTA": "https://gtfs.remix.com/dcta_denton_tx_us.zip",
    },
    umr_names=[
        "Dallas-Fort Worth-Arlington",
        "Dallas-Fort Worth-Arlington TX",
        "Dallas-Fort Worth-Arlington, TX",
    ],
)
```

### Chicago Config (Validation Example)

```python
CHICAGO = MetroConfig(
    metro_id="chicago",
    metro_name="Chicago-Naperville-Elgin MSA",
    metro_fips="16980",
    state_fips="17",
    state_abbr="IL",
    counties={
        "Cook": "031",
        "DuPage": "043",
        "Kane": "089",
        "Kendall": "093",
        "Lake": "097",
        "McHenry": "111",
        "Will": "197",
    },
    center=(41.88, -87.63),
    zoom=8,
    transit_agencies={
        "50066": "Chicago Transit Authority",
        "50064": "Metra",
        "50065": "Pace",
    },
    gtfs_feeds={
        "CTA": "https://www.transitchicago.com/downloads/sch_data/google_transit.zip",
        "Metra": "https://schedule.metrarail.com/gtfs/schedule/feed.zip",
        "Pace": "https://www.pacebus.com/sites/default/files/GTFS/google_transit.zip",
    },
    umr_names=[
        "Chicago-Naperville",
        "Chicago-Naperville IL-IN-WI",
        "Chicago-Naperville, IL-IN-WI",
    ],
)
```

### Registry

```python
METRO_REGISTRY: dict[str, MetroConfig] = {
    "dfw": DFW,
    "chicago": CHICAGO,
}


def get_metro(metro_id: str) -> MetroConfig:
    """Look up a metro config by ID. Raises KeyError if not found."""
    if metro_id not in METRO_REGISTRY:
        available = sorted(METRO_REGISTRY.keys())
        raise KeyError(f"Unknown metro '{metro_id}'. Available: {available}")
    return METRO_REGISTRY[metro_id]
```

### Backward Compatibility

During migration, `geography.py` stays but becomes a thin wrapper:

```python
# geography.py — deprecated, import from metro.py instead
from urbanstack.metro import DFW

DFW_STATE_FIPS = DFW.state_fips
DFW_COUNTY_FIPS = DFW.counties
```

This lets extractors migrate one at a time without breaking the others.

---

## 4. Extract Layer Refactoring

Every extractor changes in three ways:

1. **Function signature**: Accept `MetroConfig` as a parameter (after `settings`).
2. **Replace geography imports**: Use `config.state_fips`, `config.counties`, etc. instead of `DFW_STATE_FIPS`, `DFW_COUNTY_FIPS`.
3. **File naming**: Output paths include `metro_id` instead of hardcoded `dfw`.

### 4.1 ACS (`extract/acs.py`)

**Current**: Imports `DFW_COUNTY_FIPS` from `geography`. Hardcodes `state:48` in Census API params. Output: `acs_county_2023.parquet`.

**Target**:

```python
def extract_acs(
    settings: Settings,
    metro: MetroConfig,                  # NEW
    granularity: Granularity = "county",
    year: int = 2023,
    *,
    force: bool = False,
) -> pl.DataFrame:
```

Changes:
- `_fetch_county()` and `_fetch_block_groups()` accept `metro: MetroConfig` instead of importing `DFW_COUNTY_FIPS`.
- API param `"in": "state:48"` becomes `f"in": f"state:{metro.state_fips}"`.
- County codes: `metro.counties.values()` instead of `DFW_COUNTY_FIPS.values()`.
- Output path: `staging/{metro.metro_id}/acs/acs_{granularity}_{year}.parquet`.
- Raw cache path: `raw/{metro.metro_id}/acs/acs_{granularity}_{year}.json`.

### 4.2 FARS (`extract/fars.py`)

**Current**: Imports `DFW_COUNTY_FIPS`, `DFW_STATE_FIPS`. Filters national FARS ZIP to DFW counties. Output: `fars_dfw_{start}_{end}.parquet`.

**Target**:

```python
def extract_fars(
    settings: Settings,
    metro: MetroConfig,
    start_year: int = 2015,
    end_year: int = 2022,
    *,
    force: bool = False,
) -> pl.DataFrame:
```

Changes:
- `state_code = metro.state_fips_int` instead of `int(DFW_STATE_FIPS)`.
- `county_codes = {int(fips) for fips in metro.counties.values()}`.
- Output: `staging/{metro.metro_id}/fars/fars_{metro.metro_id}_{start}_{end}.parquet`.
- Note: FARS downloads are national ZIPs — the raw file stays in `raw/fars/` (shared across metros to avoid re-downloading). Only the filtered output is metro-scoped.

### 4.3 NTD (`extract/ntd.py`)

**Current**: Hardcodes `DFW_TRANSIT_AGENCIES` dict. Output: `ntd_dfw.parquet`.

**Target**:

```python
def extract_ntd(
    settings: Settings,
    metro: MetroConfig,
    *,
    force: bool = False,
) -> pl.DataFrame:
```

Changes:
- Remove `DFW_TRANSIT_AGENCIES` constant — use `metro.transit_agencies` instead.
- Loop: `for ntd_id in metro.transit_agencies:`.
- Output: `staging/{metro.metro_id}/ntd/ntd_{metro.metro_id}.parquet`.

### 4.4 UMR (`extract/umr.py`)

**Current**: Hardcodes `DFW_NAMES` list for filtering. Output: `umr_dfw.parquet`.

**Target**:

```python
def extract_umr(
    settings: Settings,
    metro: MetroConfig,
    *,
    force: bool = False,
) -> pl.DataFrame:
```

Changes:
- Remove `DFW_NAMES` — use `metro.umr_names`.
- `_filter_dfw()` → `_filter_metro(df, metro)`.
- Error message: reference `metro.umr_names` instead of `DFW_NAMES`.
- Output: `staging/{metro.metro_id}/umr/umr_{metro.metro_id}.parquet`.
- Note: Raw UMR Excel contains all metros — shared download, metro-specific filter.

### 4.5 FHWA (`extract/fhwa.py`)

**Current**: Imports `DFW_STATE_FIPS`, uses it to filter TMAS data. Output: `fhwa_tx_{year}.parquet`.

**Target**:

```python
def extract_fhwa(
    settings: Settings,
    metro: MetroConfig,
    year: int = 2023,
    *,
    force: bool = False,
) -> pl.DataFrame:
```

Changes:
- `_fetch_month()` uses `metro.state_fips` instead of `DFW_STATE_FIPS`.
- Output: `staging/{metro.metro_id}/fhwa/fhwa_{metro.state_abbr.lower()}_{year}.parquet`.
- Note: FHWA data is state-level (no county field in API). The county filter happens in the transform layer via spatial join with station locations.

### 4.6 EPA SLD (`extract/epa_sld.py`)

**Current**: Imports `DFW_COUNTY_FIPS`, `DFW_STATE_FIPS`. Filters national CSV to DFW block groups. Output: `epa_sld_dfw.parquet`.

**Target**:

```python
def extract_epa_sld(
    settings: Settings,
    metro: MetroConfig,
    *,
    force: bool = False,
) -> pl.DataFrame:
```

Changes:
- Filter: `metro.state_fips` and `metro.county_fips_set` instead of `DFW_STATE_FIPS` and `DFW_COUNTY_FIPS.values()`.
- Output: `staging/{metro.metro_id}/epa_sld/epa_sld_{metro.metro_id}.parquet`.
- Note: Raw CSV is national (~170 MB) — shared download, metro-specific filter.

### 4.7 GTFS (`extract/gtfs.py`)

**Current**: Hardcodes `GTFS_FEEDS` dict with DFW agencies. Output: `gtfs_routes.parquet`, etc.

**Target**:

```python
def extract_gtfs(
    settings: Settings,
    metro: MetroConfig,
    agencies: list[str] | None = None,
    *,
    force: bool = False,
) -> dict[str, pl.DataFrame]:
```

Changes:
- Remove `GTFS_FEEDS` constant — use `metro.gtfs_feeds`.
- Feed lookup: `metro.gtfs_feeds.get(agency)`.
- Output: `staging/{metro.metro_id}/gtfs/gtfs_routes.parquet`, etc.

### 4.8 Gazetteer (`extract/gazetteer.py`)

**Current**: Imports `DFW_COUNTY_FIPS`, `DFW_STATE_FIPS`. Filters national Gazetteer to DFW counties. Output: `gazetteer_dfw.parquet`.

**Target**:

```python
def extract_gazetteer(
    settings: Settings,
    metro: MetroConfig,
    *,
    force: bool = False,
) -> pl.DataFrame:
```

Changes:
- GEOID filter: `metro.county_fips_5_set` instead of hardcoded set.
- Output: `staging/{metro.metro_id}/gazetteer/gazetteer_{metro.metro_id}.parquet`.
- Note: Raw Gazetteer is national — shared download.

### 4.9 USAspending (`extract/usaspending.py`)

**Current**: Imports `DFW_COUNTY_FIPS`, `DFW_STATE_FIPS`. Builds county FIPS list for API filter. Output: `usaspending_dfw_{start}_{end}.parquet`.

**Target**:

```python
def extract_usaspending(
    settings: Settings,
    metro: MetroConfig,
    start_year: int = 2020,
    end_year: int = 2024,
    *,
    defc: str | None = None,
    force: bool = False,
) -> pl.DataFrame:
```

Changes:
- County filter: `list(metro.county_fips_5_set)` instead of manual list comprehension.
- Output: `staging/{metro.metro_id}/usaspending/usaspending_{metro.metro_id}_{start}_{end}.parquet`.

### 4.10 TMAS Stations (`extract/tmas_stations.py`)

**Current**: Hardcodes `state='TX'` in ArcGIS query. References `dfw_counties.geojson` via relative path. Output: `tmas_stations_dfw.parquet`.

**Target**:

```python
def extract_tmas_stations(
    settings: Settings,
    metro: MetroConfig,
    *,
    force: bool = False,
) -> pl.DataFrame:
```

Changes:
- ArcGIS query: `f"state='{metro.state_abbr}'"`.
- GeoJSON path: resolved from metro config (see Section 6 for boundary file conventions).
- Output: `staging/{metro.metro_id}/tmas_stations/tmas_stations_{metro.metro_id}.parquet`.

### Summary of Shared vs. Metro-Specific Raw Downloads

| Source | Raw Download Scope | Shared? |
|---|---|---|
| Census ACS | State-level API calls | No — API params differ per metro |
| FARS | National ZIPs | Yes — filter in Python |
| NTD | Per-agency API calls | No |
| UMR | National Excel | Yes — filter rows |
| FHWA TMAS | State-level API calls | No — state param differs |
| EPA SLD | National CSV | Yes — filter rows |
| GTFS | Per-agency ZIPs | No |
| Gazetteer | National ZIP | Yes — filter rows |
| USAspending | Per-county API calls | No |
| TMAS Stations | State-level API call | No |

Shared raw files stay in `data/raw/{source}/` (not metro-scoped). Metro-specific raw files go in `data/raw/{metro_id}/{source}/`.

---

## 5. Transform Layer Refactoring

### 5.1 County Mart (`transform/county_mart.py`)

**Current**: Filters ACS by `DFW_STATE_FIPS`. Reads staging files from flat `staging/{source}/` paths. Reads UMR from `umr_dfw.parquet`. Writes JSON to `web/public/data/county_summary.json`.

**Target**:

```python
def build_county_mart(
    settings: Settings,
    metro: MetroConfig,
    *,
    force: bool = False,
) -> pl.DataFrame:
```

Changes:
- Remove `from urbanstack.geography import DFW_STATE_FIPS`.
- ACS filter: `metro.state_fips` instead of `DFW_STATE_FIPS`.
- All staging reads: `settings.staging_dir / metro.metro_id / "acs" / ...` instead of `settings.staging_dir / "acs" / ...`.
- Mart output: `settings.marts_dir / metro.metro_id / "county_summary.parquet"`.
- JSON output: `web/public/data/{metro.metro_id}/county_summary.json`.
- `build_year_overlays()` also takes `metro: MetroConfig`. Overlay output: `web/public/data/{metro.metro_id}/overlays/`.

### 5.2 Block Group Mart (`transform/block_group_mart.py`)

**Current**: Filters by `DFW_STATE_FIPS`. References `dfw_block_groups.geojson` by name for FARS spatial join.

**Target**:

```python
def build_block_group_mart(
    settings: Settings,
    metro: MetroConfig,
    *,
    force: bool = False,
) -> pl.DataFrame:
```

Changes:
- ACS filter: `metro.state_fips`.
- GeoJSON path: `web/public/data/{metro.metro_id}/{metro.metro_id}_block_groups.geojson` (or a config-driven lookup — see Section 6).
- All staging reads: metro-scoped paths.
- Mart output: `settings.marts_dir / metro.metro_id / "block_group_summary.parquet"`.
- JSON output: `web/public/data/{metro.metro_id}/block_group_summary.json`.

### 5.3 Metro Mart (`transform/metro_mart.py`)

**Current**: Hardcodes `METRO_FIPS = "48DFW"` and `METRO_NAME = "Dallas-Fort Worth-Arlington MSA"`.

**Target**:

```python
def build_metro_mart(
    settings: Settings,
    metro: MetroConfig,
    *,
    force: bool = False,
) -> pl.DataFrame:
```

Changes:
- Remove `METRO_FIPS` and `METRO_NAME` constants.
- Use `metro.metro_fips` and `metro.metro_name` in the result dict.
- UMR path: metro-scoped (`staging/{metro.metro_id}/umr/...`).
- NTD path: metro-scoped.
- Output: `settings.marts_dir / metro.metro_id / "metro_summary.parquet"`.
- JSON: `web/public/data/{metro.metro_id}/metro_summary.json`.

### 5.4 No Changes Required

- **`transform/derived.py`**: Declarative metric registry — operates on column names, not geography. No changes.
- **`transform/spatial.py`**: Point-in-polygon module — accepts any GeoJSON boundaries. No changes.

---

## 6. Data Directory Structure

### Current

```
data/
  raw/
    acs/
    fars/
    ...
  staging/
    acs/
    fars/
    ...
  marts/
    county_summary.parquet
    block_group_summary.parquet
    metro_summary.parquet
    urbanstack.duckdb
```

### Target

```
data/
  raw/
    # Shared national downloads (one copy, filtered per metro)
    fars/FARS2022NationalCSV.zip
    epa_sld/sld_v3.csv
    umr/complete-data-umr.xlsx
    gazetteer/2024_Gaz_counties_national.txt

    # Metro-specific raw data
    dfw/
      acs/acs_county_2023.json
      ntd/ntd_dfw.json
      fhwa/fhwa_tx_2023.json
      gtfs/dart_gtfs.zip
      tmas_stations/tmas_stations_tx.json
      usaspending/usaspending_dfw_2020_2024.json
    chicago/
      acs/acs_county_2023.json
      ntd/ntd_chicago.json
      ...

  staging/
    dfw/
      acs/acs_county_2023.parquet
      fars/fars_dfw_2015_2022.parquet
      ntd/ntd_dfw.parquet
      umr/umr_dfw.parquet
      fhwa/fhwa_tx_2023.parquet
      epa_sld/epa_sld_dfw.parquet
      gtfs/gtfs_routes.parquet
      gazetteer/gazetteer_dfw.parquet
      usaspending/usaspending_dfw_2020_2024.parquet
      tmas_stations/tmas_stations_dfw.parquet
    chicago/
      acs/acs_county_2023.parquet
      ...

  marts/
    dfw/
      county_summary.parquet
      block_group_summary.parquet
      metro_summary.parquet
    chicago/
      county_summary.parquet
      ...
    national/
      county_summary.parquet    # union of all metros
      metro_summary.parquet     # one row per metro
    urbanstack.duckdb           # all tables, all metros
```

### Boundary GeoJSON Files (Web)

```
web/public/data/
  dfw/
    counties.geojson
    block_groups.geojson
    county_summary.json
    block_group_summary.json
    metro_summary.json
    overlays/
      index.json
      county_2015.json
      ...
    transit_routes.geojson
    transit_stops.geojson
  chicago/
    counties.geojson
    ...
```

### Settings Changes

`Settings` gains a helper for metro-scoped paths:

```python
@dataclass(frozen=True)
class Settings:
    census_api_key: str = ""
    data_dir: Path = field(default_factory=lambda: Path("data"))

    # Existing properties unchanged
    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def staging_dir(self) -> Path:
        return self.data_dir / "staging"

    @property
    def marts_dir(self) -> Path:
        return self.data_dir / "marts"

    # New helpers for metro-scoped paths
    def metro_raw_dir(self, metro_id: str) -> Path:
        return self.raw_dir / metro_id

    def metro_staging_dir(self, metro_id: str) -> Path:
        return self.staging_dir / metro_id

    def metro_marts_dir(self, metro_id: str) -> Path:
        return self.marts_dir / metro_id
```

Extractors use `settings.metro_staging_dir(metro.metro_id) / "acs" / ...` for output. Shared raw files still use `settings.raw_dir / "fars" / ...`.

---

## 7. National Dataset Design

### Per-Metro Marts to National Tables

Each metro's mart builder produces a `county_summary.parquet` (and block group, metro) scoped to that metro. A `metro_id` column is added during the mart build:

```python
# In build_county_mart(), before writing:
base = base.with_columns(pl.lit(metro.metro_id).alias("metro_id"))
```

National tables are created by concatenating all per-metro marts:

```python
# pipeline/src/urbanstack/transform/national.py

def build_national_county_mart(settings: Settings) -> pl.DataFrame:
    """Union all per-metro county marts into a national table."""
    metro_dirs = sorted(settings.marts_dir.glob("*/county_summary.parquet"))
    frames = [pl.read_parquet(p) for p in metro_dirs]
    national = pl.concat(frames)
    out = settings.marts_dir / "national" / "county_summary.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    national.write_parquet(out)
    return national


def build_national_metro_mart(settings: Settings) -> pl.DataFrame:
    """Union all per-metro metro-level summaries into a single table."""
    metro_dirs = sorted(settings.marts_dir.glob("*/metro_summary.parquet"))
    frames = [pl.read_parquet(p) for p in metro_dirs]
    national = pl.concat(frames)
    out = settings.marts_dir / "national" / "metro_summary.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    national.write_parquet(out)
    return national
```

### DuckDB Serving Layer

`load/duckdb_loader.py` evolves to load all metro marts plus national tables:

```python
def load_marts(settings: Settings) -> duckdb.DuckDBPyConnection:
    db_path = settings.marts_dir / "urbanstack.duckdb"
    conn = duckdb.connect(str(db_path))

    # Load per-metro tables
    for metro_dir in sorted(settings.marts_dir.iterdir()):
        if not metro_dir.is_dir():
            continue
        metro_id = metro_dir.name
        for parquet_file in sorted(metro_dir.glob("*.parquet")):
            table_name = f"{metro_id}__{parquet_file.stem}"
            conn.execute(
                f'CREATE OR REPLACE TABLE "{table_name}" '
                "AS SELECT * FROM read_parquet(?)",
                [str(parquet_file)],
            )

    # Load national tables
    national_dir = settings.marts_dir / "national"
    if national_dir.exists():
        for parquet_file in sorted(national_dir.glob("*.parquet")):
            conn.execute(
                f'CREATE OR REPLACE TABLE "{parquet_file.stem}" '
                "AS SELECT * FROM read_parquet(?)",
                [str(parquet_file)],
            )

    return conn
```

### Future API Layer

When the web moves beyond static JSON, a lightweight API server queries DuckDB:

```
GET /api/data?metro=dfw&granularity=county
GET /api/data?granularity=metro  (all metros)
GET /api/data?lat=32.78&lon=-96.85&zoom=8  (auto-detect metro)
```

This replaces static JSON files and enables cross-metro queries. DuckDB can query Parquet files directly without an import step, which simplifies the serving layer during development.

---

## 8. Web Refactoring

### 8.1 Rename Components

| Current | Target | File |
|---|---|---|
| `DFWMap` | `ChoroplethMap` | `components/ChoroplethMap.tsx` |
| `INITIAL_VIEW` (hardcoded) | `viewportFromConfig(metro)` | `lib/metro.ts` |
| "DFW Urban Data Explorer" | `${metro.metro_name} Urban Data Explorer` | `app/page.tsx` |

### 8.2 Metro Config in TypeScript

```typescript
// web/src/lib/metro.ts

export interface MetroConfig {
  metro_id: string;
  metro_name: string;
  center: [number, number];  // [lat, lon]
  zoom: number;
}

// Phase 1: static config (matches Python registry)
export const METROS: Record<string, MetroConfig> = {
  dfw: {
    metro_id: "dfw",
    metro_name: "Dallas-Fort Worth-Arlington MSA",
    center: [32.78, -96.85],
    zoom: 8,
  },
  chicago: {
    metro_id: "chicago",
    metro_name: "Chicago-Naperville-Elgin MSA",
    center: [41.88, -87.63],
    zoom: 8,
  },
};

// Phase 2: load from API
// export async function loadMetroConfig(): Promise<MetroConfig[]> { ... }
```

### 8.3 Data Path Parameterization

```typescript
// web/src/lib/data.ts — updated

function dataPath(metroId: string, granularity: Granularity): string {
  return `/data/${metroId}/${granularity}_summary.json`;
}

function geoJsonPath(metroId: string, granularity: Granularity): string {
  const file = granularity === "block_group" ? "block_groups" : "counties";
  return `/data/${metroId}/${file}.geojson`;
}
```

When the API layer is ready, these become fetch calls to `/api/data?metro=...`.

### 8.4 Metro Selector UI

Add a metro selector to the header bar, before the granularity selector:

```tsx
<select
  value={selectedMetro}
  onChange={(e) => setSelectedMetro(e.target.value)}
>
  {Object.entries(METROS).map(([id, config]) => (
    <option key={id} value={id}>
      {config.metro_name}
    </option>
  ))}
</select>
```

When selectedMetro changes, reload data and update viewport:

```tsx
useEffect(() => {
  const metro = METROS[selectedMetro];
  setViewport({
    latitude: metro.center[0],
    longitude: metro.center[1],
    zoom: metro.zoom,
  });
  // reload data for new metro
}, [selectedMetro]);
```

### 8.5 Complete File Changes

| File | Change |
|---|---|
| `components/DFWMap.tsx` | Rename to `ChoroplethMap.tsx`. Remove `INITIAL_VIEW` constant. Accept `viewport` prop. |
| `components/TransitLayer.tsx` | No change — already generic (loads from GeoJSON files) |
| `components/TrafficLayer.tsx` | No change — already generic |
| `components/ComparisonChart.tsx` | No change — data-driven |
| `components/CountyDetail.tsx` | No change — data-driven |
| `components/MetricSelector.tsx` | No change — data-driven |
| `components/MapControls.tsx` | No change |
| `lib/data.ts` | Parameterize `DATA_FILES` and `GEOJSON_FILES` with `metroId`. Add `loadMetros()`. |
| `lib/metro.ts` | New file — `MetroConfig` interface and registry |
| `app/page.tsx` | Add `selectedMetro` state. Update imports (`DFWMap` → `ChoroplethMap`). Dynamic title. |

---

## 9. CLI / Orchestrator

Add a CLI entry point using Python's `argparse` (no external dependency needed).

**File**: `pipeline/src/urbanstack/cli.py`

```python
import argparse
import logging
import sys

from urbanstack.config import load_settings
from urbanstack.metro import METRO_REGISTRY, get_metro


def main() -> None:
    parser = argparse.ArgumentParser(prog="urbanstack", description="UrbanStack pipeline CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    # --- extract ---
    ex = sub.add_parser("extract", help="Run one or all extractors for a metro")
    ex.add_argument("--metro", required=True, choices=sorted(METRO_REGISTRY))
    ex.add_argument("--source", default="all", help="Source name or 'all'")
    ex.add_argument("--year", type=int, default=None)
    ex.add_argument("--force", action="store_true")

    # --- transform ---
    tr = sub.add_parser("transform", help="Build mart tables for a metro")
    tr.add_argument("--metro", required=True, choices=sorted(METRO_REGISTRY))
    tr.add_argument("--force", action="store_true")

    # --- national ---
    sub.add_parser("national", help="Build national union tables from all metro marts")

    # --- load ---
    sub.add_parser("load", help="Import all marts into DuckDB")

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    settings = load_settings()
    settings.ensure_dirs()

    if args.command == "extract":
        metro = get_metro(args.metro)
        _run_extract(settings, metro, args.source, args.year, force=args.force)
    elif args.command == "transform":
        metro = get_metro(args.metro)
        _run_transform(settings, metro, force=args.force)
    elif args.command == "national":
        _run_national(settings)
    elif args.command == "load":
        _run_load(settings)
```

Register the CLI in `pyproject.toml`:

```toml
[project.scripts]
urbanstack = "urbanstack.cli:main"
```

Usage:

```bash
urbanstack extract --metro dfw --source acs --year 2023
urbanstack extract --metro dfw --source all
urbanstack extract --metro chicago --source all --force
urbanstack transform --metro dfw
urbanstack transform --metro chicago
urbanstack national
urbanstack load
```

The `_run_extract()` function dispatches to individual extractors via a registry dict:

```python
EXTRACTORS = {
    "acs": extract_acs,
    "fars": extract_fars,
    "ntd": extract_ntd,
    "umr": extract_umr,
    "fhwa": extract_fhwa,
    "epa_sld": extract_epa_sld,
    "gtfs": extract_gtfs,
    "gazetteer": extract_gazetteer,
    "usaspending": extract_usaspending,
    "tmas_stations": extract_tmas_stations,
}
```

---

## 10. Migration Path

Each step keeps DFW working. No big-bang migration.

### Phase 1: MetroConfig Foundation

1. Create `pipeline/src/urbanstack/metro.py` with `MetroConfig` dataclass and `DFW` instance.
2. Make `geography.py` a thin wrapper that imports from `metro.py`.
3. Add `metro_raw_dir()`, `metro_staging_dir()`, `metro_marts_dir()` helpers to `Settings`.
4. Verify: `make test` — all existing tests pass.

### Phase 2: Migrate Extractors (One at a Time)

For each extractor, in any order:
1. Add `metro: MetroConfig` parameter.
2. Replace geography imports with `metro.*` properties.
3. Update output paths to include `metro.metro_id`.
4. Update test fixtures.
5. Verify: `make test`, then run the extractor manually for DFW.

Recommended order (simplest first):
1. `gazetteer.py` — minimal logic, good proof of pattern.
2. `usaspending.py` — small, clear FIPS replacement.
3. `acs.py` — core extractor, validates county/state_fips pattern.
4. `fars.py` — shared national download pattern.
5. `ntd.py` — transit agency lookup pattern.
6. `umr.py` — name-matching filter pattern.
7. `epa_sld.py` — large shared download pattern.
8. `fhwa.py` — state-level data pattern.
9. `gtfs.py` — multi-feed pattern.
10. `tmas_stations.py` — spatial join + GeoJSON path pattern.

### Phase 3: Migrate Marts

1. Refactor `county_mart.py` — accept `MetroConfig`, metro-scoped paths.
2. Refactor `block_group_mart.py` — same.
3. Refactor `metro_mart.py` — same, replace `METRO_FIPS`/`METRO_NAME`.
4. Add `metro_id` column to all mart outputs.
5. Verify: Full DFW pipeline end-to-end.

### Phase 4: CLI Orchestrator

1. Create `cli.py` with argparse.
2. Add `[project.scripts]` to `pyproject.toml`.
3. Test: `urbanstack extract --metro dfw --source all`.

### Phase 5: Validate with Chicago

1. Add `CHICAGO` to `METRO_REGISTRY`.
2. Source Chicago boundary GeoJSON files.
3. Run: `urbanstack extract --metro chicago --source all`.
4. Run: `urbanstack transform --metro chicago`.
5. Debug data issues — each source may have Chicago-specific quirks.

### Phase 6: Web Refactoring

1. Rename `DFWMap.tsx` → `ChoroplethMap.tsx`.
2. Create `lib/metro.ts` with TypeScript `MetroConfig`.
3. Parameterize data paths in `lib/data.ts`.
4. Add metro selector dropdown to `page.tsx`.
5. Move viewport to metro config.
6. Update titles and labels.

### Phase 7: National Tables

1. Create `transform/national.py`.
2. Add `urbanstack national` CLI command.
3. Update `duckdb_loader.py` for multi-metro tables.

### Phase 8: API Layer

1. Add a lightweight HTTP server (FastAPI or similar) that queries DuckDB.
2. Replace static JSON fetches with API calls in the web app.
3. Support `?metro=dfw`, `?metro=chicago`, and national queries.

### Phase 9: National Map UI

1. Default view: US map showing all metros as points.
2. Click a metro to zoom in and load its data.
3. Metro comparison view: side-by-side metrics across metros.

---

## 11. What Stays City-Specific (Always)

These will never be generic — each metro has unique values:

| Element | Why |
|---|---|
| Transit agency NTD IDs and names | Every metro has different agencies |
| GTFS feed URLs | Each agency publishes its own feed |
| UMR metro name variations | TTI uses inconsistent naming |
| County FIPS codes | By definition unique per metro |
| Boundary GeoJSON files | Geometry is metro-specific |
| Map viewport (center + zoom) | Geographic coordinates |
| TMAS station locations | Physical infrastructure |

All of these live inside `MetroConfig` instances. Adding a new metro means adding a new `MetroConfig` — no code changes required.

---

## 12. What's Truly Generic (Shared Forever)

These modules work for any metro without modification:

| Module | Why |
|---|---|
| `contracts/*.py` | Schema validation is geography-independent |
| `transform/spatial.py` | Point-in-polygon works with any GeoJSON |
| `transform/derived.py` | Metric registry is pure column math |
| `_socrata.py` | Pagination helper — API-agnostic |
| `utils.py` | File utilities |
| `config.py` | Settings dataclass (extended, not changed) |
| All web visualization components | Data-driven — no geography in the render logic |
| Color scales, format utilities | Math, not geography |

### Data Source Fetching Patterns

The actual data-fetching logic (Census API, FARS ZIP parsing, Socrata pagination, etc.) is source-specific but geography-independent. The same code fetches ACS data for any state/county combo — only the parameters change. This is already true in the current code; the refactoring simply externalizes the parameters into `MetroConfig`.

---

## Appendix: Contracts — No Changes Needed

For completeness, the contracts that remain untouched:

- `contracts/acs.py` — `AcsRecord` uses generic `state_fips`, `county_fips` fields
- `contracts/fars.py` — `FarsCrashRecord` has `state_fips`, `county_fips` fields
- `contracts/ntd.py` — `NtdRidershipRecord` uses `ntd_id`, not a metro reference
- `contracts/umr.py` — `UmrRecord` uses `urban_area` string field
- `contracts/fhwa.py` — `FhwaVolumeRecord` uses `state_fips`, `station_id`
- `contracts/epa_sld.py` — `EpaSldRecord` uses `state_fips`, `county_fips`, `geoid`
- `contracts/gtfs.py` — `GtfsRoute`, `GtfsStop`, `GtfsShape` use `agency` string
- `contracts/gazetteer.py` — `GazetteerRecord` uses `county_fips`, `state_abbr`
- `contracts/usaspending.py` — `UsaspendingCountyRecord` uses `county_fips`
- `contracts/tmas_stations.py` — `TmasStationRecord` uses `station_id`, `county_fips`

All models define schemas by shape (field names and types), not by geography. They validate any metro's data correctly.
