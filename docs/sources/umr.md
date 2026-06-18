# Texas A&M Urban Mobility Report (UMR)

## Source

Texas A&M Transportation Institute (TTI), Urban Mobility Report.

- Report page: https://mobility.tamu.edu/umr/report/
- Data download: https://tti.tamu.edu/documents/umr/data/complete-data-2025-umr-by-tti.xlsx

## Fields Extracted

| Source Column | Contract Field | Description |
|---|---|---|
| Urban Area | urban_area | Metro area name |
| Year | year | Data year (1982-2024) |
| Travel Time Index | travel_time_index | Ratio of peak travel time to free-flow time |
| Planning Time Index | planning_time_index | Extra time needed for reliable trips (95th percentile) |
| Annual Delay per Auto Commuter (hours) | annual_delay_per_commuter | Hours lost per commuter per year |
| Congestion Cost per Auto Commuter (dollars) | congestion_cost_per_commuter | Dollar cost per commuter per year |
| Total Delay (1,000 person-hours) | total_delay_thousand_hours | Metro-wide total delay |
| Total Excess Fuel Consumed (1,000 gallons) | total_excess_fuel_thousand_gallons | Metro-wide excess fuel from congestion |

## Update Frequency

Annual. Published mid-year, typically covering data through the prior calendar year.

## Geographic Coverage

Filtered to Dallas-Fort Worth-Arlington metro area. The full dataset covers 494 US urban areas.

## Data Acquisition

The extractor first attempts to download the Excel spreadsheet from TTI's website. If that fails (network issues, URL change), it falls back to reading a manually-placed file from `data/raw/umr/`.

### Manual Download Instructions

1. Visit https://mobility.tamu.edu/umr/report/
2. Download the "congestion data spreadsheet" (Excel, ~2 MB)
3. Place in `data/raw/umr/` (any `.xlsx` or `.csv` filename)
4. Run the extractor: `uv run python -c "from urbanstack.extract.umr import extract_umr; from urbanstack.config import load_settings; extract_umr(load_settings())"`

## Historical Coverage

1982-2024 for the 101 largest US urban areas. Additional 393 urban areas covered from 2017-2024.

## Join Key

`urban_area` + `year`. The UMR uses metro area names (not FIPS codes), so joining to census data requires a crosswalk on metro area name.
