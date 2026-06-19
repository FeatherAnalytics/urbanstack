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
| `DFWMap` | Main deck.gl + MapLibre choropleth map |
| `MetricSelector` | Dropdown to pick active metric (grouped by category) |
| `ComparisonChart` | Horizontal bar chart ranking counties/block groups |
| `CountyDetail` | Sidebar detail panel for selected county |
| `MapControls` | Toggle overlays (traffic, rail, bus) |
| `TrafficLayer` | TomTom traffic flow tile layer (auto-refreshes) |
| `TransitLayer` | GTFS rail/bus route + stop GeoJSON layers |
| `ThemeToggle` | Dark/light mode with localStorage persistence |

## Data Flow

- Static JSON/GeoJSON in `public/data/` — no API calls for core data
- `lib/data.ts` — metric configs, types (`CountyData`, `MetricConfig`), color interpolation, formatting
- GeoJSON files: `dfw_counties.geojson`, `dfw_block_groups.geojson` (~27MB, lazy-loaded), `transit_routes.geojson`, `transit_stops.geojson`
- Summary JSONs: `county_summary.json`, `block_group_summary.json`, `metro_summary.json`
- Adding a metric: one entry in `lib/data.ts` METRICS array + corresponding field in summary JSON
