# UrbanStack — Future Development

## Architecture: Multi-City Expansion

The current DFW pilot establishes patterns that generalize to any metro:

- **Geography module** (`geography.py`) — swap FIPS codes and county list for a new metro
- **Spatial module** (`transform/spatial.py`) — accepts any GeoJSON boundaries + any point data
- **Derived metrics** (`transform/derived.py`) — declarative registry; metrics auto-compute wherever required columns exist
- **Extract layer** — each source module is parameterized by state/county/metro identifiers
- **Web** — `MetricConfig` array + `hasData()` filtering means new metrics appear automatically when data exists

### To add a new city
1. Define metro geography (state FIPS, county FIPS list, boundary GeoJSON)
2. Run existing extractors with new geography config
3. Transforms auto-produce marts with all available metrics
4. Web loads from the same JSON structure — no frontend changes needed

## Planned Features

### Block Group Year Overlays
Currently year-specific data (FARS by year, NTD by year) only available at county level as static JSON overlays. Block group overlays deferred because 4,400+ rows per year produces large JSON files.

**When to build:** When a proper data backend exists (DuckDB API route, or Snowflake).

**Approach:** API route that accepts `{granularity, year}` and queries the database, returning only the year-varying fields merged with base data. Eliminates static JSON files entirely.

### Data Backend
Current architecture: Python pipeline → static JSON → Next.js static fetch.

**Target architecture:**
- DuckDB (or Snowflake) as serving layer
- Next.js API routes query the database with granularity + year + metro params
- Enables: arbitrary year selection, cross-metro comparison, real-time data updates
- Eliminates: pre-computed JSON files, overlay merge logic on the frontend

### Additional Data Sources (Candidates)
| Source | Coverage | Grain | Notes |
|--------|----------|-------|-------|
| Census TIGER/Line | National | Block group | Land area polygons for pop density |
| LEHD LODES | National | Block group | Employment origin-destination flows |
| HUD CHAS | National | County/tract | Housing affordability and cost burden |
| BLS QCEW | National | County | Employment and wages by industry |
| EPA EJScreen | National | Block group | Environmental justice indicators |
| USDOT Safety Data (CRSS) | National | Event-level | Non-fatal crash data (complements FARS) |
| BTS Transportation Noise | National | Raster / tract | Modeled highway, aviation, and rail noise levels (dB) |
| NLCD Tree Canopy / Landsat NDVI | National | 30m raster → block group | Vegetation greenness and tree canopy cover |
| Trust for Public Land ParkServe | National | Block group | Park access: % population within 10-min walk of a park |

### Transportation Noise (BTS)
DOT's Bureau of Transportation Statistics publishes the **National Transportation Noise Map** — modeled noise levels (dB LAeq) from highway traffic, aviation, and rail for the entire US.

**Data sources:**
- **ArcGIS map service** at [maps.dot.gov/BTS/NationalTransportationNoiseMap](https://maps.dot.gov/BTS/NationalTransportationNoiseMap/) — queryable raster tiles showing noise contours (45–80+ dB). Can overlay directly or sample via spatial query.
- **Census tract-level downloads** from [University of Washington DEOHS](https://deohs.washington.edu/national-transportation-noise-exposure-map-download) — population exposure estimates by dB band per tract. CSV format, joinable to existing tract/block-group data via GEOID.
- **BTS data inventory** at [data.bts.gov](https://data.bts.gov/stories/s/National-Transportation-Noise-Map/ri89-bhxh/) — metadata, methodology docs, vintage info.

**Integration approach:**
- **Tabular (tract-level):** Download UW DEOHS tract-level CSVs → new extract module `extract/noise.py` → join to block group mart via tract GEOID prefix (block group GEOID starts with its parent tract GEOID). Metrics: avg dB exposure, % population above 55 dB (EPA threshold), % above 65 dB (HUD threshold).
- **Raster (visualization):** Query ArcGIS tile service directly from deck.gl as a `TileLayer` (same pattern as TomTom traffic tiles). No pipeline needed — purely a frontend overlay toggle.
- **Derived metrics:** Noise-safety correlation (crash rate vs noise level as proxy for traffic volume), noise equity index (noise exposure weighted by income).

**Why it fits:** Noise is a direct proxy for traffic intensity and a recognized public health indicator. Complements existing walkability (EPA SLD), crash data (FARS), and congestion metrics (UMR). National coverage means it scales to all-US in Phase 3.

### Vegetation Greenness (NDVI / Tree Canopy)
Satellite-derived vegetation indices measure greenery at the block group level. Research shows strong relationships between urban greenery and noise — dense tree canopy reduces traffic noise 3–7 dB over 15–20m, and a 1% increase in green view index correlates with a 2% decrease in noise complaints (NYC longitudinal study).

**Data sources:**
- **USGS NLCD Tree Canopy** — 30m resolution percent tree canopy cover for the entire US. Available from [MRLC](https://www.mrlc.gov/). Most directly actionable: download national raster, compute mean % canopy per block group via zonal statistics.
- **USGS Landsat NDVI** — 30m resolution normalized vegetation index from [Landsat Collection 2](https://www.usgs.gov/landsat-missions/landsat-normalized-difference-vegetation-index). Higher fidelity than MODIS (250m) for urban areas. Use summer peak (April–September) max composite.
- **NASA MODIS NDVI** — 250m, 16-day composites from [NASA Earthdata](https://www.earthdata.nasa.gov/topics/land-surface/normalized-difference-vegetation-index-ndvi). Coarser but simpler to process. Good enough for county-level analysis.
- **EPA EnviroAtlas** — Pre-computed % tree cover and % green space at block group level for [~1,400 cities](https://www.epa.gov/enviroatlas/data-download). Not nationally comprehensive but zero raster processing needed for covered cities.
- **Trust for Public Land ParkServe** — [Block group level](https://www.tpl.org/park-data-downloads) park access metrics: % population within 10-min walk of a park, park acres per 1,000 residents. National coverage. Complementary to NDVI (park access ≠ greenness).

**Integration approach:**
- **Preferred:** Download NLCD Tree Canopy national GeoTIFF → new extract module `extract/tree_canopy.py` → use `rasterstats` library to compute mean % canopy per block group polygon → join to block group mart via GEOID.
- **Alternative:** Use EnviroAtlas pre-computed data where available, fall back to NLCD for uncovered areas.
- **Metrics:** Mean % tree canopy, mean NDVI, park access score (ParkServe).
- **Derived metrics:**
  - **Noise-greenery gap:** Block groups with high noise + low greenery = priority areas for urban canopy investment. Formula: `noise_dB_normalized - canopy_pct_normalized` (positive = underserved).
  - **Green equity index:** Canopy % weighted by income quintile — do lower-income block groups have less canopy?
  - **Environmental quality composite:** Combine walkability (EPA SLD) + canopy + noise + crash rate into a single index.

**Why it fits:** Greenery is the natural complement to noise data — research confirms the physical and perceptual relationship. Together they tell a story about livability that neither tells alone. NLCD is free, national, and 30m resolution. The `rasterstats` zonal computation is a one-time batch job, not a recurring API call.

**References:**
- [Influence of Green Areas on Urban Sound Environment (Springer, 2023)](https://link.springer.com/article/10.1007/s40726-023-00284-5)
- [Urban Environment and Noise Perception, NYC (Springer, 2025)](https://link.springer.com/article/10.1007/s44212-025-00093-9)
- [Tree Characteristics and Noise in Montreal (ScienceDirect, 2021)](https://www.sciencedirect.com/science/article/abs/pii/S0013935121011828)

### Time Series Visualization
Sidebar feature: small range chart showing data coverage per source. Data sources on y-axis, time on x-axis. Shows which years each source covers and allows visual comparison of temporal overlap.

### H3 Hexagonal Indexing (Phase 2)
**Decision:** Adopt for point data only. Keep Census geography for tabular data.

- Use `h3-py` + `h3ronpy` (Polars-native) for spatial indexing of FARS crashes, TMAS stations, GTFS stops
- Resolution 8 (~460m edges) for urban analysis
- Do NOT interpolate ACS demographics into hex cells — that's fabrication, not analysis
- Hybrid approach: H3 for point events, Census FIPS for demographics, crosswalk table to link them
- deck.gl has native `H3HexagonLayer` — no GeoJSON needed for hex visualization
- Timing: after core pipeline stable and tested

### Pandana Network Accessibility
- Add walkability/transit accessibility scoring via Pandana (C++ core, fast)
- Feed OSM street networks via osmnet
- Metrics: "minutes to nearest transit stop", "jobs within 30 min drive"
- Pairs with OSM street networks for route-based analysis

### OSM Street Networks + Live Traffic
- Extract walkable/drivable networks via osmnet for any metro
- Combine with TomTom live traffic tiles for real-time congestion on actual road segments
- Route-based accessibility analysis (not just distance)

### GeoParquet
- Write spatial data as GeoParquet in marts (emerging standard)
- Loads into both Polars and GeoPandas without conversion
- Future-proofs data interchange

### dataId-Based Dataset Registry (Frontend)
- Pattern from Kepler.gl: each data source registers with stable ID
- Layers/filters reference by ID, decoupling data loading from visualization
- Better architecture for multi-metro, multi-source UI

### Mobile-Friendly Responsive Design
**Status:** V1 shipped (slide-out sidebar overlay, compact header selects, full-width map). See `feature/ux-polish` branch.

**Remaining work for V2:**
- Bottom sheet drawer with swipe gestures (pull-up panel) for metric selector and county detail
- Touch-friendly map controls (larger tap targets, minimum 44px per WCAG)
- Map viewport adapts — tighter initial zoom on mobile
- Test on iOS Safari and Chrome Android — deck.gl WebGL has mobile-specific quirks
- Lazy-load comparison chart until user requests it

### Frontend UX Improvements
- Collapsible metric category sections in sidebar
- Color scale legend on map
- Calculation formula tooltip on hover for derived metrics
- Stronger visual distinction between estimated vs measured metrics

### Regional Granularity (Multi-Metro Regions)

Currently the hierarchy is: All US → Metro → County → Block Group. A natural next step is grouping metros into **regions** for higher-level comparison.

**Example regions:**
- **Texas Triangle:** DFW + Houston + San Antonio + Austin
- **Northeast Corridor:** NYC + Boston + Philadelphia + Washington DC
- **Great Lakes:** Chicago + Minneapolis + Detroit + Milwaukee
- **California Megaregion:** SF + LA + San Diego + Sacramento

**Implementation approach:**
1. Add `RegionConfig` to `lib/metro.ts` — a region is a named collection of metro IDs with a viewport (center + zoom for the combined area)
2. Add `"region"` to the `Granularity` type — slots between "All US" and "Metro Area" in the scale selector
3. Region-level data = aggregation of constituent metro summaries. Pipeline computes `region_summary.json` by summing/averaging metro-level values (population-weighted for rates)
4. Region GeoJSON = merged boundaries of constituent metros (convex hull or union)
5. ComparisonChart shows metros within the selected region, or regions in the "All US" view

**Key questions to resolve:**
- Which region definitions to use? BEA Economic Areas, Census Combined Statistical Areas (CSAs), or custom groupings?
- CSAs are official (NYC-Newark CSA, DFW-Texoma CSA) but some are very large. Custom groupings allow thematic comparisons (Sun Belt vs Rust Belt, car-dependent vs transit-rich)
- Should regions be user-definable? Interesting for exploration but complex UI
- How to handle metros that belong to multiple regions? (e.g., DC is both Northeast Corridor and Mid-Atlantic)

**When to build:** After 6+ metros are in the system. With only 3 metros, regions are trivial. At 8-10 metros, regional patterns become analytically meaningful.

### Share URL Tracking

Shareable URLs were added in the `feature/ux-polish` branch (`?metro=dfw&metric=pct_transit`). Tracking which URLs are shared and viewed enables a "what's interesting" heatmap.

**Architecture options:**

1. **Lightweight: UTM parameters + static analytics**
   - Append UTM params when generating share links: `?metro=dfw&metric=pct_transit&utm_source=share&utm_medium=link`
   - Use Plausible, Fathom, or Umami (privacy-respecting, no cookies) to track page views with query params
   - Dashboard shows which metros, metrics, and combos are most shared/viewed
   - **Pros:** Zero backend, privacy-friendly, works with static hosting
   - **Cons:** No unique share tracking, just aggregate views

2. **Medium: Cloudflare Workers + KV**
   - Share button generates a short ID via Cloudflare Worker → stores `{id, metro, metric, granularity, timestamp}` in KV
   - Short URL: `featheranalytics.dev/s/abc123` → Worker redirects to full URL, increments view count
   - Worker logs: `{share_id, viewer_ip_hash, timestamp, referer}` → KV or D1 (SQLite)
   - **Pros:** Per-share tracking, view counts, referrer data. D1 is free tier. Already using Cloudflare (R2)
   - **Cons:** Requires Worker deployment, maintains state

3. **Full: Share + heatmap visualization**
   - Build on option 2. Store geographic context (which county/metro was centered) with each share
   - Aggregate shares into H3 hexagons or county FIPS counts
   - New "Shares" layer toggle on the map — heatmap of what areas people find interesting
   - Could weight by views (viral shares vs one-off)
   - **Pros:** Compelling meta-visualization ("what do people care about?")
   - **Cons:** Needs meaningful volume to be interesting. Privacy considerations (don't expose individual shares)

**Recommended path:** Start with option 1 (Plausible/Umami analytics — one `<script>` tag). Upgrade to option 2 when share volume justifies it. Option 3 is a compelling portfolio feature but needs volume.

**Data to capture per share event:**
- `metro`, `metric`, `granularity`, `year` from URL params
- Timestamp, referrer, approximate geo (from analytics)
- View count per unique share URL
- Optional: user-provided title/annotation ("Check out DFW's pedestrian fatality rate")

### CI / CD Pipeline

Currently deployment is a single GitHub Action (`deploy.yml`) that builds the pipeline, exports data, builds the frontend, and deploys to GitHub Pages. No CI validation on feature branches.

**Recommended CI setup:**

1. **On every push to feature branches:**
   - `npm run lint` — catch lint errors before merge
   - `npx vitest run` — run all tests
   - `npm run build` — verify production build succeeds (catches TypeScript errors, missing imports)
   - Lighthouse CI (`@lhci/cli`) — track accessibility score ≥ 92, flag regressions

2. **On PR to main:**
   - All of the above plus:
   - Preview deployment to Cloudflare Pages (or Vercel preview) — reviewers can see the actual site
   - Bundle size check — flag if JS bundle grows > 10%

3. **On merge to main:**
   - Existing deploy.yml handles data export + GitHub Pages deployment
   - Add deployment verification: curl the live URL, check for 200 status

**GitHub Action for feature branches:**

```yaml
name: CI
on:
  push:
    branches-ignore: [main]
  pull_request:
    branches: [main]

jobs:
  validate:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: web
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 22 }
      - run: npm ci
      - run: npm run lint
      - run: npx vitest run
      - run: npm run build
```

**When to add:** Now — this is low effort, high value. The lint + test + build check prevents broken merges.

### Derived Metric Ideas (Future)
- Transit access score (EPA SLD walkability + transit frequency + ridership)
- Crash severity index (fatalities / crashes — higher = deadlier crashes)
- Commute burden (commute mode share weighted by avg commute time, when ACS commute time data added)
- Infrastructure ROI (federal spending vs congestion cost reduction over time — requires multi-year comparison)
