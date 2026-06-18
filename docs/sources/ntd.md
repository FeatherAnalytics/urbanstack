# NTD Monthly Ridership

## Source

Federal Transit Administration (FTA), National Transit Database (NTD).

- Portal: https://www.transit.dot.gov/ntd
- API: Socrata SODA API at `https://data.transportation.gov/resource/8bui-9xvu.json`
- Dataset: Complete Monthly Ridership (with Adjustments and Estimates)

## Fields Extracted

| API Column | Contract Field | Description |
|-----------|---------------|-------------|
| ntd_id | ntd_id | NTD agency identifier |
| agency | agency_name | Transit agency name |
| mode | mode | Transit mode code (LR=Light Rail, MB=Bus, DR=Demand Response, CR=Commuter Rail, etc.) |
| date | year, month | Parsed from ISO 8601 date field |
| upt | unlinked_passenger_trips | Unlinked Passenger Trips (ridership count) |
| vrm | vehicle_revenue_miles | Vehicle Revenue Miles |
| vrh | vehicle_revenue_hours | Vehicle Revenue Hours |

## DFW Transit Agencies

| NTD ID | Agency | Notes |
|--------|--------|-------|
| 60056 | Dallas Area Rapid Transit (DART) | Light rail, bus, paratransit |
| 60086 | Trinity Metro | Fort Worth bus and commuter rail (formerly "The T" / FWTA) |
| 60166 | Denton County Transportation Authority (DCTA) | A-train commuter rail, bus |

## Update Frequency

Monthly. Agencies report ridership monthly; NTD publishes updated data with a ~2 month lag. Historical data back to 2002.

## API Query Pattern

```
GET /resource/8bui-9xvu.json
  ?$where=ntd_id='60056'
  &$limit=50000
  &$offset=0
  &$order=date
```

Queried per agency with pagination ($offset) to stay within Socrata limits.

## Rate Limits

No API key required. Unauthenticated requests are throttled by Socrata.

## Join Key

`ntd_id` identifies the agency. `mode` + `date` provide the grain (one row per agency per mode per month).
