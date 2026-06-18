# NHTSA FARS Traffic Fatalities

## Source

National Highway Traffic Safety Administration (NHTSA), Fatality Analysis Reporting System (FARS).

- Portal: https://www.nhtsa.gov/research-data/fatality-analysis-reporting-system-fars
- API: https://crashviewer.nhtsa.dot.gov/CrashAPI/

## Fields Extracted

| API Column | Contract Field | Description |
|-----------|---------------|-------------|
| ST_CASE | case_id | Unique crash case identifier (state+year) |
| STATE | state_fips | State FIPS code (always "48" for Texas) |
| COUNTY | county_fips | County FIPS code, zero-padded to 3 digits |
| YEAR | year | Crash year |
| MONTH | month | Crash month (1-12) |
| FATALS | fatalities | Number of fatalities (always >= 1 in FARS) |
| PERSONS | persons | Total persons involved |
| PEDS | pedestrians | Pedestrians involved |
| DRUNK_DR | drunk_drivers | Number of drunk drivers |
| LATITUDE | latitude | Crash latitude (sentinel values nullified) |
| LONGITUD | longitude | Crash longitude (field name varies by year: LONGITUD or LONGITUDE) |

## Update Frequency

Annual. FARS data is finalized approximately 18 months after the calendar year ends. Preliminary Annual Release Files (ARF) may appear earlier. Available years: 2010-2022 reliably; 2023 may be available.

## Geographic Coverage

DFW metro area counties only. The extractor queries per-county per-year using standard FIPS county codes from `geography.py`.

## API Query Pattern

Per-county per-year via GetCrashesByLocation:

```
GET /CrashAPI/crashes/GetCrashesByLocation
  ?fromCaseYear=2022&toCaseYear=2022
  &state=48&county=113
  &format=json
```

Response is nested JSON: `{"Results": [{"Results": [...crashes...]}]}`. The extractor unwraps this structure automatically.

## County Codes

FARS uses standard FIPS county codes. The API accepts integer county codes (e.g., 113 for Dallas). The raw response returns county as an integer; the extractor zero-pads to 3 digits for consistency with geography.py.

## Coordinate Handling

FARS uses sentinel values for missing coordinates (77.7777, 88.8888, 99.9999, 0.0). The extractor nullifies these.

## Rate Limits

No API key required. The extractor adds a 1-second delay between requests. Queries are scoped to single county+year to stay under the 5000-record limit.

## Join Key

`county_fips` + `year` for aggregate joins with ACS/SLD data. `latitude`/`longitude` for spatial analysis when coordinates are available.
