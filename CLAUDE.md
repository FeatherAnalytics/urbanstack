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

## File Organization

- `pipeline/` — Python ETL (extract → validate → transform → load)
- `web/` — Next.js + deck.gl frontend
- `data/` — Local storage (gitignored): raw/, staging/, marts/
- `docs/sources/` — One doc per data source
- `thoughts/` — Internal decision notes

## Common Commands

```bash
make setup          # Install all dependencies
make test           # Run all tests
make lint           # Run linters
make format         # Auto-format Python code
make dev            # Start web dev server
```
