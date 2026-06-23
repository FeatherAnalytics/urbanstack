# Plan: National-Scale Data Architecture

**Date**: 2026-06-23
**Goal**: Serve all 3,143 US counties and 242,180 block groups in the browser with near-zero infrastructure cost.
**Stack**: PMTiles + DuckDB-WASM + Cloudflare R2 + GitHub Pages

---

## Current State

- 3 metros (DFW, Chicago, NYC) served via static JSON/GeoJSON in `web/public/data/`
- Block group GeoJSON: 27–54 MB per metro, loaded entirely into browser memory
- Block group summary JSON: 6–23 MB per metro, fetched as single file
- deck.gl renders via `GeoJsonLayer` — no tiling
- No deployment pipeline — local dev only
- Pipeline outputs Parquet → JSON → `web/public/data/`

## Target State

- All US counties and block groups renderable in browser
- Geometry streamed as vector tiles (PMTiles on R2) — browser loads only visible area
- Key metrics embedded in tile properties for choropleth coloring
- Full attribute data queried via DuckDB-WASM against remote Parquet on R2 (Phase 3 only — when national data justifies it)
- Next.js static export on GitHub Pages (HTML/JS/CSS only, no data files)
- Total hosting cost: ~$0–5/month

---

## Phase 1: GitHub Pages Deployment

**Goal**: Get CI/CD working with current data. Foundation for everything else.

### Changes

1. **`web/next.config.ts`** — Add static export config:
   ```typescript
   const nextConfig: NextConfig = {
     output: "export",
     basePath: "/urbanstack",
     images: { unoptimized: true },
   };
   ```

2. **Traffic API route** — `web/src/app/api/traffic/` won't work in static export. Options:
   - Remove traffic layer for static deploy (simplest)
   - Call TomTom tile API directly with CORS (if supported)
   - Move to Cloudflare Worker (Phase 2 anyway)

3. **`.github/workflows/deploy.yml`** — GitHub Actions workflow:
   - Checkout → install deps → `npm run build` → deploy `out/` to GitHub Pages
   - Triggered on push to `main`

4. **Verify** — Site loads at `https://featheranalytics.github.io/urbanstack/`

### Files

| Action | File |
|--------|------|
| Modify | `web/next.config.ts` |
| Create | `.github/workflows/deploy.yml` |
| Modify or remove | `web/src/app/api/traffic/` |

### Decision: Data files in repo?

Current GeoJSON files total ~150 MB across 3 metros. GitHub Pages serves from repo — these files inflate repo size. Two options:

- **A) Keep for now** — deploy works immediately, worry about R2 later
- **B) Move data to R2 in this phase** — cleaner but more setup upfront

Recommend: **A**. Ship deployment first, optimize later.

---

## Phase 2: PMTiles for Block Group Geometry

**Goal**: Replace 27–54 MB GeoJSON loads with streamed vector tiles. Biggest performance win.

### Prerequisites

- `brew install tippecanoe` (local)
- Cloudflare account with R2 bucket created
- R2 CORS configured for GitHub Pages origin + localhost

### Pipeline Changes

1. **`pipeline/src/urbanstack/cli.py`** — Add `urbanstack export --metro <id>` command:
   - Reads existing GeoJSON from `web/public/data/{metroId}/block_groups.geojson`
   - Runs Tippecanoe → outputs to `exports/{metroId}_block_groups.pmtiles`
   - Embeds top ~5 metrics (population, median_income, avg_walkability, commute_drive_alone_pct, total_fatalities) as tile properties for choropleth coloring without a separate data fetch
   ```python
   # yagni: inline in cli.py, extract to export/ module when there are 3+ export formats
   subprocess.run([
       "tippecanoe", "-ab", "-z12", "-Z3",
       "--coalesce-densest-as-needed",
       "-o", str(output_path),
       "-l", layer_name,
       str(geojson_path)
   ], check=True)
   ```

2. **`Makefile`** — Add `upload-r2` target:
   ```makefile
   # yagni: Makefile target, create scripts/upload_to_r2.sh when logic grows
   upload-r2:
   	aws s3 cp exports/ s3://urbanstack-data/ \
   	  --endpoint-url https://$${CF_ACCOUNT_ID}.r2.cloudflarestorage.com \
   	  --recursive
   ```

### Frontend Changes

3. **`web/package.json`** — Add `@loaders.gl/pmtiles` dependency (verify first: may ship with deck.gl 9.3.4 already)

4. **`web/src/components/ChoroplethMap.tsx`** — Replace block group rendering:
   ```typescript
   // Replace GeoJsonLayer with MVTLayer for block groups
   import { MVTLayer } from "@deck.gl/geo-layers";

   new MVTLayer({
     id: "block-groups",
     data: `${R2_BASE_URL}/${metroId}_block_groups.pmtiles`,
     // ... fill/stroke/picking config stays same
   })
   ```
   Keep `GeoJsonLayer` for counties (small enough — 6–35 KB).
   Tile properties now carry embedded metrics — choropleth coloring reads directly from tile features, no separate JSON fetch needed for block groups.

5. **`web/src/lib/data.ts`** — Remove `loadGeoJSON()` for block groups. Keep for counties. Add R2 base URL as a const:
   ```typescript
   // yagni: inline const, create config.ts when there are 3+ config values
   export const R2_BASE_URL = process.env.NEXT_PUBLIC_R2_URL
     ?? "https://urbanstack-data.{account}.r2.dev";
   ```

### R2 Setup

8. **Cloudflare Dashboard** → Create R2 bucket `urbanstack-data`
9. **CORS policy** on bucket:
   ```json
   [{
     "AllowedOrigins": ["https://featheranalytics.github.io", "http://localhost:3000"],
     "AllowedMethods": ["GET", "HEAD"],
     "AllowedHeaders": ["Range"],
     "ExposeHeaders": ["Content-Range", "Content-Length"]
   }]
   ```
10. **Public access** — Enable R2 public bucket URL (or custom domain)

### Files

| Action | File |
|--------|------|
| Modify | `pipeline/src/urbanstack/cli.py` (add export command) |
| Modify | `Makefile` (add upload-r2 target) |
| Modify | `web/package.json` (add @loaders.gl/pmtiles if not bundled with deck.gl) |
| Modify | `web/src/components/ChoroplethMap.tsx` (GeoJsonLayer → MVTLayer for block groups) |
| Modify | `web/src/lib/data.ts` (remove block group GeoJSON load, add R2_BASE_URL) |

### Verify

- NYC block groups render from R2 PMTiles
- Pan/zoom loads tiles on demand (no 54 MB upfront load)
- County layer still works (unchanged)
- Metric coloring still works (attributes joined client-side)

---

## Phase 3: Scale to All US + DuckDB-WASM

**Goal**: Extract and serve all 3,143 counties and 242,180 block groups. Add DuckDB-WASM for attribute queries — justified now because 50–80 MB national Parquet can't be served as static JSON.

> **Why DuckDB-WASM lives here (not earlier):** With only 3 metros, embedded tile properties + small JSON summaries handle coloring and detail panels. At national scale, JSON summaries reach 50+ MB — DuckDB-WASM with HTTP range reads becomes the right tool. yagni: don't add a 4 MB WASM dependency until data volume demands it.

### Pipeline Changes

1. **Expand extraction** — Census ACS API supports national queries. Modify extract modules to pull all states/counties instead of per-metro FIPS lists.

2. **National geometry** — Download TIGER/Line block group shapefiles for all 50 states + DC. Convert to single GeoJSON → Tippecanoe → PMTiles.
   - Expected: ~1.9 GB GeoJSON → ~100–200 MB PMTiles

3. **National Parquet** — Union all block group data into one Parquet file. Add to `cli.py` export command:
   ```python
   # yagni: inline in cli.py, extract to module when export has 3+ formats
   def build_national_parquet(metros: list[str], output_dir: Path) -> None:
       frames = []
       for metro_id in metros:
           df = pl.read_parquet(marts_dir / metro_id / "block_group_summary.parquet")
           df = df.with_columns(pl.lit(metro_id).alias("metro_id"))
           frames.append(df)
       pl.concat(frames).write_parquet(output_dir / "block_groups.parquet")
   ```
   - Expected: ~50–80 MB Parquet (242K rows × 50 columns)

4. **Remove per-metro silos** — Single national PMTiles + single national Parquet replaces per-metro files.

5. **Metro config** — `metro.ts` becomes a "fly to" shortcut for discovery, not a data filter. All data is national. Don't remove — users landing on a national map need entry points.

### Frontend Changes

6. **`web/package.json`** — Add `@duckdb/duckdb-wasm`

7. **`web/src/lib/duckdb.ts`** — DuckDB initialization + query helpers:
   ```typescript
   import * as duckdb from "@duckdb/duckdb-wasm";

   let db: duckdb.AsyncDuckDB;

   export async function initDuckDB(): Promise<void> {
     // Initialize WASM worker
     // Register remote Parquet files on R2
   }

   export async function queryBlockGroups(
     metroId?: string,
     geoids?: string[]
   ): Promise<CountyData[]> {
     // SQL query against registered Parquet
     // Filter by metro_id or geoid list — not viewport bounding box
   }
   ```
   > yagni: query by metro_id or geoid list, not viewport bounding box. Spatial queries add complexity (bbox → GEOID mapping). Metro-scoped loads + national county view covers 90% of use cases. Add spatial filtering only if users report slow loads.

8. **`web/src/lib/data.ts`** — Replace `loadData()` for block groups:
   ```typescript
   export async function loadData(metroId: string, granularity: Granularity) {
     if (granularity === "block_group") {
       return queryBlockGroups(metroId);
     }
     // County/metro: still small enough for static JSON
   }
   ```

9. **Metro selector** — Repurpose as "fly to" dropdown. Selecting a metro: viewport flies to metro bounds + DuckDB queries filter by `metro_id`.

### Data Sources That Need National Expansion

| Source | Current Scope | National Effort |
|--------|--------------|-----------------|
| ACS | 3 metro FIPS lists | Single national API call — easy |
| EPA SLD | Per-metro download | National file available — easy |
| FARS | Per-state | All states — moderate |
| GTFS | Per-agency | 800+ agencies — significant |
| NTD | Per-metro | National download — easy |
| FHWA | Per-state | All states — moderate |
| UMR | Per-metro | 100 metros covered — moderate |
| USASpending | Per-metro | National query — easy |

### Files

| Action | File |
|--------|------|
| Modify | All extract modules (national scope) |
| Modify | `pipeline/src/urbanstack/geography.py` (all FIPS) |
| Modify | `pipeline/src/urbanstack/cli.py` (add national Parquet export) |
| Modify | `Makefile` (add upload-r2 for Parquet) |
| Create | `web/src/lib/duckdb.ts` |
| Modify | `web/package.json` (add @duckdb/duckdb-wasm) |
| Modify | `web/src/lib/data.ts` (DuckDB queries for block groups) |
| Modify | `web/src/lib/metro.ts` (repurpose as "fly to" shortcuts) |
| Modify | `web/src/components/ChoroplethMap.tsx` (remove metro-based data filtering) |

### Estimated Data Sizes (National)

| Asset | Size on R2 | Browser Load |
|-------|-----------|--------------|
| `us_block_groups.pmtiles` | 100–200 MB | ~1–3 MB per viewport |
| `us_counties.pmtiles` | ~5 MB | ~200 KB per viewport |
| `block_groups.parquet` | 50–80 MB | ~2–5 MB per query |
| `county_summary.parquet` | ~1.5 MB | Full load OK |
| DuckDB-WASM bundle | — | ~4 MB (one-time, lazy-loaded) |

---

## Infrastructure Summary

| Component | Service | Cost |
|-----------|---------|------|
| App hosting | GitHub Pages | Free |
| Data hosting | Cloudflare R2 | ~$0–3/mo (10 GB free, $0 egress) |
| Domain (optional) | Cloudflare | $10/year |
| CI/CD | GitHub Actions | Free (2,000 min/mo) |
| **Total** | | **$0–5/month** |

## New Dependencies

| Package | Phase | Bundle Impact |
|---------|-------|---------------|
| `@loaders.gl/pmtiles` | 2 (verify: may ship with deck.gl 9.3.4) | ~50 KB |
| `@duckdb/duckdb-wasm` | 3 (not before — yagni until national data) | ~4 MB WASM (lazy-loaded) |
| `tippecanoe` (CLI) | 2, build-time only | n/a |
| `aws` CLI or `rclone` | 2, build-time only | n/a |

## Risk & Mitigation

| Risk | Mitigation |
|------|------------|
| PMTiles range requests blocked by CORS | Test CORS config early in Phase 2 |
| DuckDB-WASM 4 MB bundle too large for first load | Lazy-load: init DuckDB only when user interacts with filters |
| Tippecanoe simplification drops small block groups | Test with `-pk` flag (no tile size limit) |
| deck.gl MVTLayer + PMTiles integration issues | deck.gl 9.x has native PMTiles support via loaders.gl |
| National ACS extraction hits Census API rate limits | Add backoff/retry, cache raw responses |

## YAGNI Decisions

Reviewed 2026-06-23. These simplifications are intentional — upgrade paths noted.

| Decision | Rationale | Upgrade When |
|----------|-----------|-------------|
| No `config.ts` — R2 URL inline in `data.ts` | One constant doesn't need its own file | 3+ config values |
| No `export/` package — Tippecanoe call inline in `cli.py` | 6-line subprocess call | 3+ export formats |
| No `scripts/upload_to_r2.sh` — Makefile target | One `aws s3 cp` command | Conditional logic or multi-bucket needed |
| No DuckDB-WASM until Phase 3 | 3 metros fit in embedded tile properties + small JSON | National data (50+ MB JSON) |
| No viewport spatial queries — filter by metro_id | Metro-scoped loads cover 90% of use | Users report slow national loads |
| Metro selector stays — repurposed as "fly to" | Users need entry points on a national map | Never remove |

## Open Questions

- UNCONFIRMED: Does deck.gl 9.3.4 bundle `@loaders.gl/pmtiles` already? Check before adding dep.
- UNCONFIRMED: Can DuckDB-WASM do HTTP range reads against R2 Parquet directly, or need `httpfs` extension?
- Decision needed: Which ~5 metrics to embed in tile properties? (Candidates: population, median_income, avg_walkability, commute_drive_alone_pct, total_fatalities)
- Decision needed: Keep transit GeoJSON as-is or also tile it?
