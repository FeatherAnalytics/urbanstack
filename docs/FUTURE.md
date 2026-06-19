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

### Frontend UX Improvements
- Collapsible metric category sections in sidebar
- Color scale legend on map
- Calculation formula tooltip on hover for derived metrics
- Stronger visual distinction between estimated vs measured metrics
- Responsive improvements for mobile

### Derived Metric Ideas (Future)
- Transit access score (EPA SLD walkability + transit frequency + ridership)
- Crash severity index (fatalities / crashes — higher = deadlier crashes)
- Commute burden (commute mode share weighted by avg commute time, when ACS commute time data added)
- Infrastructure ROI (federal spending vs congestion cost reduction over time — requires multi-year comparison)
