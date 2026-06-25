@AGENTS.md

## Stack

Next.js 16 + React 19 + TypeScript, deck.gl 9 + MapLibre + react-map-gl, Tailwind 4.

## Commands

```bash
npm run dev     # Dev server (port 3000)
npm run build   # Production build (static export)
npm run lint    # ESLint
```

## Components

| Component | Purpose |
|-----------|---------|
| `ChoroplethMap` | Main deck.gl + MapLibre choropleth map (multi-metro via viewport prop) |
| `MetricSelector` | Dropdown to pick active metric (grouped by category) |
| `ComparisonChart` | Horizontal bar chart ranking counties/block groups |
| `CountyDetail` | Sidebar detail panel for selected county |
| `MapControls` | Toggle overlays (traffic, rail, bus) |
| `TrafficLayer` | TomTom traffic flow tile layer (auto-refreshes) |
| `TransitLayer` | GTFS rail/bus route + stop GeoJSON layers |
| `ThemeToggle` | Dark/light mode with localStorage persistence |

## Data Flow

- Static JSON/GeoJSON in `public/data/{metroId}/` — no API calls for core data
- `lib/metro.ts` — metro registry (`MetroConfig`, `METROS`, `DEFAULT_METRO`)
- `lib/data.ts` — metric configs, types (`CountyData`, `MetricConfig`), color interpolation, formatting, bivariate combos, `INTERSECTION_DENSITY_BENCHMARK` (259/sq mi)
- GeoJSON files per metro: `counties.geojson`, `block_groups.geojson` (~27MB, lazy-loaded), `transit_routes.geojson`, `transit_stops.geojson`
- Summary JSONs per metro: `county_summary.json`, `block_group_summary.json`, `metro_summary.json`
- Adding a metric: one entry in `lib/data.ts` METRICS array + corresponding field in summary JSON (categories: Demographics, Transportation, Safety, Spending, Congestion, Public Space)
- Adding a metro: one entry in `lib/metro.ts` METROS + data files in `public/data/{metroId}/`
