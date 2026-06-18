# GTFS Transit Routes

## Source

General Transit Feed Specification (GTFS) static feeds from DFW transit agencies.

| Agency | Feed URL |
|---|---|
| DART | https://www.dart.org/transitdata/latest/google_transit.zip |
| Trinity Metro | http://sched.ridetm.org/gtfs/fwtatransitdata.zip |
| DCTA | https://gtfs.remix.com/dcta_denton_tx_us.zip |

## Files Extracted

### routes.txt

| GTFS Column | Contract Field | Description |
|---|---|---|
| route_id | route_id | Agency-unique route identifier |
| route_short_name | route_short_name | Short display name (e.g., "1", "RED") |
| route_long_name | route_long_name | Full route name |
| route_type | route_type | 0=tram, 1=subway/metro, 2=rail, 3=bus, etc. |

### stops.txt

| GTFS Column | Contract Field | Description |
|---|---|---|
| stop_id | stop_id | Agency-unique stop identifier |
| stop_name | stop_name | Stop display name |
| stop_lat | latitude | WGS84 latitude |
| stop_lon | longitude | WGS84 longitude |

### shapes.txt

| GTFS Column | Contract Field | Description |
|---|---|---|
| shape_id | shape_id | Shape identifier (links to trips) |
| shape_pt_lat | latitude | WGS84 latitude |
| shape_pt_lon | longitude | WGS84 longitude |
| shape_pt_sequence | sequence | Order of points along the shape |

## Update Frequency

Varies by agency. DART and Trinity Metro update feeds with each schedule change (typically quarterly). DCTA updates less frequently.

## Geographic Coverage

DFW metroplex. DART serves Dallas and 12 surrounding cities. Trinity Metro serves Fort Worth, Richland Hills, Blue Mound, and the Grapevine Visitors Shuttle. DCTA serves Denton County with bus and A-train commuter rail.

## Data Format

Each agency publishes a ZIP file containing CSV text files per the GTFS specification. The extractor downloads ZIP files to `data/raw/gtfs/`, parses routes.txt, stops.txt, and shapes.txt, validates through contracts, and writes three Parquet files to `data/staging/gtfs/`.

## Route Types

Per GTFS spec: 0=tram/streetcar, 1=subway/metro, 2=rail, 3=bus, 4=ferry, 5=cable tram, 6=gondola, 7=funicular, 11=trolleybus, 12=monorail.

## Join Keys

- `agency` + `route_id` for routes
- `agency` + `stop_id` for stops
- `agency` + `shape_id` for shapes (shape_id links to trips.txt which links to routes.txt)
