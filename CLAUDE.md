# UrbanStack — Project Rules

## Overview

Multi-layer urban data platform: Python ETL pipeline + Next.js/deck.gl visualization.
Pilot city: Dallas-Fort Worth. Storage: local Parquet + DuckDB (Snowflake later).

## Python Rules

- Python 3.13, managed with `uv`
- Type hints on all functions — no exceptions
- `ruff` for linting and formatting (configured in pyproject.toml)
- No `# type: ignore` without a comment explaining why
- Use `polars` for dataframes (not pandas)
- Use `pydantic` for data contracts and config
- Use `dataclasses` for simple internal structures

## TypeScript Rules

- Strict mode enabled in tsconfig.json
- ESLint + Prettier configured
- No `any` without a comment explaining why
- Prefer named exports over default exports

## Data Pipeline Rules

- Every pipeline step must be idempotent — safe to re-run without duplicating data
- Schema validation on all ingested data — fail loud if source format changes
- Each data source is its own module in `pipeline/src/urbanstack/extract/`
- Raw data preserved as-is in `data/raw/` — never modify raw files
- Transformations happen in `transform/` layer, output to `data/staging/`
- Final joined tables go to `data/marts/`

## Data Contracts

- Define expected schema (columns, types, value ranges) per source in `contracts/`
- Use pydantic models for contract definitions
- Pipeline must fail if a contract is violated — don't silently ingest bad data

## Security

- All API keys and credentials in `.env` — never committed
- `.env.example` documents required vars without values
- No hardcoded file paths — use config.py or env vars
- This will be a public repo — review every file before committing

## Testing

- Tests for all transformation and ETL logic
- Data validation tests (row counts, null checks, expected value ranges)
- No test that depends on network access — mock all API responses
- Test fixtures in `tests/conftest.py`
- Run: `cd pipeline && uv run pytest`

## Git

- Conventional commits: `feat:`, `fix:`, `docs:`, `data:`, `refactor:`, `test:`
- Feature branches — no direct commits to main
- Run `/code-review` and `/yagni` before merging

## Data Sources

Each source has an extract module, pydantic contract, and doc in `docs/sources/`:

| Source | Module | Description |
|--------|--------|-------------|
| ACS | `acs` | Census demographics, income, commute mode |
| EPA SLD | `epa_sld` | Smart Location Database — walkability, transit access |
| FARS | `fars` | Fatal crash data from NHTSA |
| FHWA | `fhwa` | Federal highway statistics |
| Gazetteer | `gazetteer` | Census place/county geometry lookups |
| GTFS | `gtfs` | Transit routes and stops (DART, DCTA, Trinity Metro) |
| NTD | `ntd` | National Transit Database ridership |
| TMAS | `tmas_stations` | Traffic monitoring station locations |
| UMR | `umr` | Urban Mobility Report congestion metrics |
| USASpending | `usaspending` | Federal transportation grants |

Shared helper: `extract/_socrata.py` (Socrata API client).

## File Organization

- `pipeline/` — Python ETL (extract → validate → transform → load)
  - `extract/` — One module per data source (see table above)
  - `contracts/` — Pydantic schemas per source
  - `transform/` — Mart builders (`county_mart`, `block_group_mart`, `metro_mart`), plus `derived.py` (metric registry) and `spatial.py` (reusable spatial joins)
  - `load/duckdb_loader.py` — Parquet → DuckDB ingestion
  - `geography.py` — County FIPS/name resolution utilities
- `web/` — Next.js + deck.gl frontend
- `data/` — Local storage (gitignored): raw/, staging/, marts/
- `docs/sources/` — One doc per data source
- `thoughts/` — Internal decision notes

## Quality Standards

This is a portfolio project. Every component must be statistically sound, analytically
reliable, and production-quality.

### Data Integrity
- Never infer data from population distribution alone — only use study-supported methods
- Per-capita rates must suppress small populations (MIN_POP=100) to avoid statistical noise
- Clearly label estimated/inferred metrics vs measured data (prefix "Est." in UI)
- Show calculation formulas on hover for all derived metrics
- Date ranges must be visible — user should always know what time period data covers

### Analytical Rigor
- Cross-source derived metrics require overlapping timeframes
- Document data source, methodology, and limitations for every metric
- Derived metrics defined declaratively in `transform/derived.py` — single registry
- Spatial joins use `transform/spatial.py` — reusable across geographies

### Performance
- Pipeline must be idempotent and cacheable (skip if Parquet exists)
- Web loads must be fast — static JSON for now, API backend later
- Block group GeoJSON (~27MB) must not block initial render

### Extensibility
- All geography-specific config in `MetroConfig` (see docs/ARCHITECTURE.md)
- Adding a metric = one entry in `derived.py` + one entry in `data.ts`
- Adding a city = one `MetroConfig` instance (after refactor)
- Modules: `spatial.py`, `derived.py`, contracts — must stay geography-agnostic

### Frontend Quality
- Lighthouse accessibility score ≥ 95
- Both dark and light modes must pass contrast checks
- All form elements must have aria labels
- Responsive: desktop sidebar, mobile bottom sheet

## Common Commands

```bash
make setup          # Install all dependencies
make test           # Run all tests
make lint           # Run linters
make format         # Auto-format Python code
make dev            # Start web dev server

# Run individual pipeline steps
cd pipeline
uv run python -m urbanstack.extract.acs      # Extract single source
uv run python -m urbanstack.transform.county_mart  # Build county mart
```
