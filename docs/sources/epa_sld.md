# EPA Smart Location Database v3

## Source

U.S. Environmental Protection Agency, Smart Location Database (SLD) version 3.

- URL: https://www.epa.gov/smartgrowth/smart-location-mapping
- Download: https://edg.epa.gov/EPADataCommons/public/OA/EPA_SmartLocationDatabase_V3_Jan_2021_Final.csv

## Variables Extracted

| CSV Column | Field | Description |
|------------|-------|-------------|
| GEOID10 | geoid | 12-digit block group FIPS |
| STATEFP | state_fips | 2-digit state FIPS |
| COUNTYFP | county_fips | 3-digit county FIPS |
| TRACTCE | tract_fips | Census tract code |
| CBSA | cbsa | Core-based statistical area code |
| D1A | d1a | Gross housing unit density (units/acre) |
| D1B | d1b | Gross population density (people/acre) |
| D1C | d1c | Gross employment density (jobs/acre) |
| D2A_JPHH | d2a_jphh | Jobs per household |
| D2B_E8MIXA | d2b_e8mixa | 8-tier employment entropy |
| D3B | d3b | Street intersection density (per sq mi) |
| D5DR | d5dr | Regional destination accessibility (auto) |
| D5DE | d5de | Destination accessibility (employment) |
| D4A | d4a | Distance to nearest transit stop (meters) |
| D4D | d4d | Aggregate frequency of transit service |
| NatWalkInd | nat_walk_ind | National Walkability Index (1-20 scale) |
| Pct_AO0 | pct_ao0 | Percent zero-car households |
| AutoOwn | autoown | Average vehicles per household |

The full dataset has 90+ columns. We extract only the D-variables and walkability/auto metrics relevant to UrbanStack's transit and land use analysis.

## Update Frequency

Irregular. Version 3 released January 2021 based on 2010 Census block groups and 2017 ACS data. No fixed update schedule.

## Geographic Level

Census block group (12-digit FIPS). National coverage; pipeline filters to DFW counties only.

## File Size

~170 MB CSV (national). DFW subset: ~3,500 block groups.

## Join Key

`geoid` (12-digit block group FIPS) joins to ACS block group data via the composite FIPS code.
