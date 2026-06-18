# Census ACS 5-Year Estimates

## Source

U.S. Census Bureau, American Community Survey (ACS) 5-Year Estimates.

- URL: https://data.census.gov
- API docs: https://www.census.gov/data/developers/data-sets/acs-5year.html

## Variables Pulled

| Variable | Field | Description |
|----------|-------|-------------|
| B01003_001E | total_population | Total population |
| B19301_001E | per_capita_income | Per capita income (dollars) |
| B19013_001E | median_household_income | Median household income (dollars) |
| B08301_003E | commute_drove_alone | Workers who drove alone |
| B08301_010E | commute_transit | Workers using public transit |
| B08301_019E | commute_walked | Workers who walked |
| B08301_018E | commute_biked | Workers who biked |
| B08301_021E | commute_wfh | Workers who worked from home |
| B08201_001E | vehicles_available | Vehicles available in occupied housing units |
| B25064_001E | median_rent | Median gross rent (dollars) |
| B25077_001E | median_home_value | Median home value (dollars) |

## Update Frequency

Annual. New 5-year estimates typically released each December.

## Geographic Coverage

Dallas-Fort Worth metroplex: 12 counties in Texas (state FIPS 48).
Supports county and block group granularity.

## Join Key

FIPS code: 5-digit (state + county) for county level, 12-digit (state + county + tract + block group) for block group level.

## API Endpoint Pattern

```
https://api.census.gov/data/{year}/acs/acs5?get=NAME,{variables}&for=county:{codes}&in=state:48&key={key}
https://api.census.gov/data/{year}/acs/acs5?get=NAME,{variables}&for=block+group:*&in=state:48&in=county:{code}&key={key}
```

## Rate Limits

500 requests per day without a key, 50 requests per IP per day for unkeyed requests. With a key: no published hard limit, but add a small delay between calls when looping over counties for block groups.

Get a free key at https://api.census.gov/data/key_signup.html.
