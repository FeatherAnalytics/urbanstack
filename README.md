# UrbanStack

Multi-layer urban data platform combining transportation, infrastructure spending, walkability, demographics, and economic data — starting with the Dallas-Fort Worth metro area.

## Architecture

```
Data Sources (APIs + bulk downloads)
  → Python ETL pipeline (extract → validate → transform → load)
    → Local storage (Parquet + DuckDB)
      → Next.js + deck.gl web visualization
```

## Data Sources

| Category | Source | Granularity |
|----------|--------|------------|
| Demographics | Census ACS (density, income, commute mode) | Block group |
| Transportation | FHWA TMAS (traffic volume) | Station → county |
| Transportation | Texas A&M UMR (congestion index) | Metro area |
| Transit | NTD (ridership) | Transit agency |
| Built Environment | EPA Smart Location DB (walkability, VMT) | Block group |
| Spending | USAspending (federal infra grants) | County |
| Spending | Urban Institute (IIJA/IRA) | County |
| Housing | ACS + Social Data Commons (affordability) | Block group |
| Safety | FARS (traffic fatalities) | Lat/lon → county |
| Environment | EPA AQI (air quality) | County |

## Setup

```bash
cp .env.example .env
# Add your Census API key to .env

make setup    # Install Python + Node dependencies
make test     # Run all tests
make lint     # Run linters
make dev      # Start web dev server
```

## Project Structure

- `pipeline/` — Python data extraction, transformation, validation
- `web/` — Next.js + deck.gl interactive map visualization
- `data/` — Local data storage (gitignored)
- `docs/` — Data source documentation
