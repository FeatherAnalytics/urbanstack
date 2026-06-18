# USAspending Federal Grant Spending

## Source

U.S. Department of the Treasury, via USAspending.gov.

- Portal: https://www.usaspending.gov/
- API: `POST https://api.usaspending.gov/api/v2/search/spending_by_geography/`
- No API key required

## Endpoint

`spending_by_geography` returns aggregated federal spending per county for a given time period and set of filters.

### Request Body

```json
{
    "scope": "place_of_performance",
    "geo_layer": "county",
    "geo_layer_filters": ["48113", "48085", "48121", ...],
    "filters": {
        "time_period": [{"start_date": "2020-10-01", "end_date": "2024-09-30"}],
        "award_type_codes": ["02", "03", "04", "05"],
        "def_codes": ["Z"]
    }
}
```

### Award Type Codes

| Code | Type |
|------|------|
| 02 | Block Grant |
| 03 | Formula Grant |
| 04 | Project Grant |
| 05 | Cooperative Agreement |

### DEFC (Disaster Emergency Fund Codes)

| Code | Legislation |
|------|-------------|
| Z | Infrastructure Investment and Jobs Act (IIJA) |

DEFC filtering is optional. Omitting `def_codes` returns all grant spending regardless of funding source.

## Fields Extracted

| API Field | Contract Field | Description |
|-----------|---------------|-------------|
| shape_code | county_fips | 5-digit county FIPS (state + county) |
| display_name | county_name | County name |
| aggregated_amount | total_obligation | Total federal grant spending in dollars |
| per_capita | per_capita | Per-capita spending (provided by API) |
| population | population | County population (provided by API) |
| (derived) | fiscal_year_start | Start of query time period |
| (derived) | fiscal_year_end | End of query time period |

## Update Frequency

Near real-time. USAspending.gov updates daily from federal agency submissions.

## Rate Limits

No API key required. No documented rate limits, but responses can be slow (up to 60s for large queries).

## Join Key

`county_fips` (5-digit FIPS) joins to ACS and other county-level datasets.
