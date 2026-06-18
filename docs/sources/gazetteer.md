# Census Gazetteer Files

## Source

U.S. Census Bureau, Gazetteer Files — Counties.

- URL: https://www.census.gov/geographies/reference-files/time-series/geo/gazetteer-files.html
- Direct download: https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2023_Gazetteer/2023_Gaz_counties_national.txt

## Fields Used

| Column | Field | Description |
|--------|-------|-------------|
| GEOID | county_fips | 5-digit county FIPS (state + county) |
| USPS | state_abbr | 2-letter state abbreviation |
| NAME | county_name | County name |
| ALAND | land_area_sqm | Land area in square meters |
| AWATER | water_area_sqm | Water area in square meters |
| INTPTLAT | latitude | Latitude of internal point (centroid) |
| INTPTLONG | longitude | Longitude of internal point (centroid) |

## Update Frequency

Annual. Published alongside decennial census and ACS geographic updates.

## Geographic Coverage

National file (~3,200 counties). Filtered to 12 DFW counties at extract time.

## Join Key

5-digit county FIPS (`county_fips`). Joins directly to ACS base via `state_fips + county_fips`.

## File Format

Tab-delimited text, ~200 KB. Single download, filter locally.

## Derived Fields

- `land_area_sqmi`: land area in square miles (`land_area_sqm / 2,589,988`)
- `pop_density`: computed in county mart as `total_population / land_area_sqmi`
