# Future Development Ideas

## Multi-Year Historical Extraction

Add time-series depth to all data sources by extracting multiple years.

### What's possible

| Source | Historical Range | Implementation |
|--------|-----------------|----------------|
| Census ACS | 2009-2023 | Loop `extract_acs(year=N)` per year |
| FHWA TMAS | 2015-2023 | Already supports year param, dataset IDs mapped |
| NTD Ridership | 2002-present | Full history in one Socrata dataset |
| USAspending | 2008-present | Adjustable `time_period` in POST body |
| FARS | 2010-2022 | Already supports year range params |
| Texas A&M UMR | 1982-2024 | Single download covers full history |

### What to build

- Update county mart to accept year parameter, produce year-partitioned output
- Time-series line charts in web visualization (ridership trends, fatality trends, spending over time)
- Year selector on the map to show any single year's snapshot
- Animated "play" mode showing change over time

### Priority

Medium — current single-year snapshot tells a useful story. Time-series adds depth but doubles pipeline complexity and storage. Best tackled after core visualization is polished.

## UI Polish

### MapLibre Attribution Z-Index

The MapLibre attribution box (bottom-right corner) gets covered by deck.gl overlay layers (traffic tiles, transit routes, county choropleth). CSS `z-index` fix attempted but doesn't fully resolve because deck.gl renders on a separate canvas element that sits above the MapLibre controls. Potential fixes:
- Move attribution to a custom HTML element outside the deck.gl canvas
- Use deck.gl's `_typedArrayManagerProps` or custom rendering order
- Render attribution as a separate fixed-position div reading MapLibre's attribution data

Priority: Low — cosmetic issue, doesn't block functionality.
