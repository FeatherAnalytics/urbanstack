# Pipeline Automation Design

**Date:** 2026-07-08
**Goal:** Make adding a new metro a single-file-edit + single-command operation with built-in validation.

## Problem

Adding a metro currently requires:
1. Edit `metro.py` (Python registry)
2. Edit `metro.ts` (TypeScript registry — easy to forget, easy to get wrong)
3. Run `extract --source all` (boundaries must run first)
4. Run `transform`
5. Run `scripts/build_transit_geojson.py` + manually gzip the output
6. Run `export` (PMTiles)
7. Manually verify data loaded correctly by clicking around the UI

Six manual steps across two languages with no validation. This session hit every failure mode: missing GeoJSON, missing PMTiles, forgotten frontend registry, null columns from missing spatial joins.

## Solution

### 1. Single Source of Truth: `metro.py`

Add `region` field to `MetroConfig`:

```python
@dataclass(frozen=True)
class MetroConfig:
    # ... existing fields ...
    region: str = ""  # e.g., "mountain", "texas", "northeast", "midwest"
```

Add `REGION_CONFIGS` dict with region display metadata:

```python
REGION_CONFIGS: dict[str, RegionMeta] = {
    "texas": RegionMeta(region_name="Texas", center=(30.5, -97.0), zoom=6),
    "northeast": RegionMeta(region_name="Northeast", center=(41.5, -72.5), zoom=6),
    "midwest": RegionMeta(region_name="Midwest", center=(41.88, -87.63), zoom=7),
    "mountain": RegionMeta(region_name="Mountain", center=(40.44, -104.90), zoom=7),
}
```

`RegionMeta` is a frozen dataclass with three fields: `region_name: str`, `center: tuple[float, float]`, `zoom: int`.

Each metro gets `region="texas"` etc. Region `metro_ids` lists derived automatically from metro configs that share the same region value.

### 2. Auto-Generate `metro.ts`

New CLI command `sync-web` reads Python registries and writes `web/src/lib/metro.ts`.

```bash
urbanstack sync-web
```

Generated file:
- Header comment: `// AUTO-GENERATED from pipeline/src/urbanstack/metro.py — do not edit manually`
- `MetroConfig` interface (unchanged)
- `METROS` dict — sorted alphabetically by metro_id
- `RegionConfig` interface (unchanged)  
- `REGIONS` dict — built from `REGION_CONFIGS` + metros grouped by region
- `METRO_TO_REGION` lookup — derived from regions

Output matches current `metro.ts` structure exactly. Zero changes needed in consuming code.

### 3. Transit GeoJSON as CLI Command

Move `scripts/build_transit_geojson.py` (499 lines) into `urbanstack.extract.transit_geojson` module. Register as CLI command:

```bash
urbanstack transit-geojson --metro denver
urbanstack transit-geojson --metro all
```

Handles gzip automatically (writes both `.geojson` and `.geojson.gz`). Raw `.geojson` stays gitignored; `.gz` tracked.

Old script becomes a thin wrapper calling the module (deprecated, removed later).

### 4. The `pipeline` Command

Top-level orchestrating command:

```bash
urbanstack pipeline --metro denver        # single metro, end-to-end
urbanstack pipeline --metro all           # all metros
urbanstack pipeline --metro denver --force # re-extract everything
```

Execution order:
1. **extract** `--source all` (boundaries run first via dict ordering)
2. **transform** (county mart → block group mart → metro mart → year overlays)
3. **transit-geojson** (build + gzip)
4. **export** (PMTiles via tippecanoe)
5. **sync-web** (regenerate `metro.ts`)
6. **validate** (summary report — see below)

Each step logs progress. Failures in optional sources (UMR for small metros, transit for metros without feeds) warn but don't halt the pipeline. The `--force` flag propagates to all steps.

### 5. Validation Report

New CLI command `validate` prints a summary table for one or all metros:

```bash
urbanstack validate --metro denver
urbanstack validate --metro all
```

Output format:

```
═══ Denver-Aurora-Centennial MSA ═══
  ACS:            10 counties, 2048 block groups    ✓
  FARS:           1872 crashes                      ✓
  NTD:            1615 rows                         ✓
  UMR:            43 rows                           ✓
  FHWA:           42153 rows                        ✓
  EPA SLD:        1797 block groups                 ✓
  GTFS:           125 routes, 7570 stops            ✓
  Gazetteer:      10 counties                       ✓
  USASpending:    10 counties                       ✓
  TMAS:           38 stations                       ✓
  OSM Parks:      11689 parks                       ✓
  Boundaries:     counties.geojson ✓  block_groups.geojson ✓
  Transit GeoJSON: 1054 routes ✓  15227 stops ✓
  PMTiles:        4.7 MB                            ✓
  Marts:          county ✓  block_group ✓  metro ✓
  Null columns:   congestion (UMR missing)
  metro.ts:       synced ✓
```

Checks:
- Each staging parquet exists and has >0 rows (warns if missing)
- Each mart exists and has >0 rows
- GeoJSON files exist (counties, block_groups, transit routes/stops)
- PMTiles file exists in exports/
- Identifies columns that are all-null in marts (indicates missing source data)
- Confirms metro.ts includes this metro

Exit code 0 if all critical checks pass (marts exist, boundaries exist). Warnings (missing optional sources) don't fail.

## Files Changed

| File | Change |
|------|--------|
| `metro.py` | Add `region` field to `MetroConfig`, add `RegionMeta` dataclass, add `REGION_CONFIGS` |
| `cli.py` | Add `pipeline`, `transit-geojson`, `sync-web`, `validate` commands |
| `extract/transit_geojson.py` | New module — moved from `scripts/build_transit_geojson.py` |
| `validate.py` | New module — validation report logic |
| `sync_web.py` | New module — generates `metro.ts` from Python registry |
| `web/src/lib/metro.ts` | Becomes auto-generated (content unchanged, header added) |

## Workflow After Implementation

**Adding a new metro:**
```bash
# 1. Edit one file
vim pipeline/src/urbanstack/metro.py  # add MetroConfig + region

# 2. Run one command
cd pipeline && uv run python -m urbanstack.cli pipeline --metro cheyenne

# 3. Review validation report (printed automatically)

# 4. Commit and push
git add -A && git commit -m "feat: add Cheyenne metro"
git push  # deploy.yml handles R2 upload + site build
```

**Re-running all metros:**
```bash
cd pipeline && uv run python -m urbanstack.cli pipeline --metro all --force
```
