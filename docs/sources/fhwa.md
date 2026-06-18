# FHWA TMAS Traffic Volume

## Source

Federal Highway Administration (FHWA), Travel Monitoring Analysis System (TMAS).

- Portal: https://data.transportation.gov/stories/s/TMAS-Data-Program/katt-tac5/
- API: Socrata SODA API at `https://data.transportation.gov/resource/{dataset_id}.json`

## Fields Extracted

| API Column | Contract Field | Description |
|-----------|---------------|-------------|
| station_id | station_id | Continuous count station identifier (state-unique) |
| state_cd | state_fips | State FIPS code (always "48" for Texas) |
| fsystem_cd | functional_class | Functional classification (1=Interstate, 2=Fwy, 3=Principal Arterial, etc.) |
| rural_urban | rural_urban | R=Rural, U=Urban |
| year | year | Data year |
| month | month | Month (1-12) |
| day | day | Day of month (1-31) |
| sum(veh_count) | daily_volume | Server-side sum of hourly vehicle counts across all lanes and directions |

## Update Frequency

Monthly. State DOTs submit continuous count data to FHWA monthly. Each calendar year gets its own Socrata dataset; typically published mid-year following.

## Geographic Coverage

All Texas (state FIPS 48). The TMAS volume API does not include county codes. Station-to-county mapping requires the separate TMAS Stations Table (File Geodatabase from BTS/NTAD), which can be joined on `station_id` when available.

## Dataset IDs by Year

| Year | Socrata ID |
|------|-----------|
| 2015 | gjfe-peac |
| 2016 | qjsn-7dw8 |
| 2017 | 354n-8ysa |
| 2018 | 4z2n-nkpd |
| 2019 | 2hya-qc6x |
| 2020 | ymmm-mwzp |
| 2021 | 9fns-puia |
| 2022 | ytjj-yht4 |
| 2023 | kv7k-jsg5 |

## API Query Pattern

Server-side aggregation sums hourly counts into daily totals per station:

```
GET /resource/{dataset_id}.json
  ?$select=station_id,fsystem_cd,rural_urban,year,month,day,sum(veh_count) as daily_volume
  &$where=state_cd='48' AND month='{m}'
  &$group=station_id,fsystem_cd,rural_urban,year,month,day
  &$limit=50000
  &$offset=0
```

Queried month-by-month with pagination ($offset) to stay within Socrata limits.

## Rate Limits

No API key required. Unauthenticated requests are throttled; the extractor adds a 0.5s delay between monthly requests.

## Join Key

`station_id` (state-unique). To join with geographic data, use the TMAS Stations Table from BTS/NTAD which maps station_id to lat/lon and county FIPS.
