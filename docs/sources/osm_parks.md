# OpenStreetMap Parks

## Overview

Park and green space polygons from OpenStreetMap via the Overpass API. Used to compute park access coverage and green space per capita metrics.

## Source

- **API:** Overpass API (`https://overpass-api.de/api/interpreter`)
- **Data:** OpenStreetMap contributors (ODbL license)
- **Refresh:** On-demand; cached as Parquet after first extraction

## Tags Extracted

| OSM Tag | park_type | Description |
|---------|-----------|-------------|
| `leisure=park` | park | Public parks, urban green spaces |
| `leisure=garden` | garden | Botanical gardens, community gardens |
| `leisure=playground` | playground | Children's playgrounds |
| `landuse=recreation_ground` | recreation_ground | Sports fields, recreation areas |

## Schema

| Field | Type | Description |
|-------|------|-------------|
| `osm_id` | int | OpenStreetMap element ID |
| `name` | str \| null | Park name from OSM tags |
| `park_type` | str | One of: park, garden, playground, recreation_ground |
| `area_sqm` | float | Approximate polygon area in square meters |
| `centroid_lat` | float | Centroid latitude |
| `centroid_lon` | float | Centroid longitude |

## Pipeline

- **Extract:** `urbanstack.extract.osm_parks`
- **Contract:** `urbanstack.contracts.osm_parks.OsmParkRecord`
- **Staging:** `data/staging/{metro_id}/osm_parks/osm_parks_{metro_id}.parquet`

## Bounding Box

Computed automatically from `web/public/data/{metro_id}/counties.geojson`. No metro-specific configuration needed.

## Notes

- Area computation uses shoelace formula on projected coordinates (approximate)
- Parks without center coordinates are excluded
- Overpass `out center` returns centroids for ways/relations without full geometry download
- No API key required; rate-limited by Overpass server
