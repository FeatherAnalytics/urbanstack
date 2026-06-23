.PHONY: setup test lint format dev export-tiles upload-r2 clean

setup: setup-pipeline setup-web

setup-pipeline:
	cd pipeline && uv sync

setup-web:
	cd web && npm install

test: test-pipeline test-web

test-pipeline:
	cd pipeline && uv run pytest

test-web:
	cd web && npm test --passWithNoTests 2>/dev/null || true

lint: lint-pipeline lint-web

lint-pipeline:
	cd pipeline && uv run ruff check src/ tests/

lint-web:
	cd web && npm run lint 2>/dev/null || true

format:
	cd pipeline && uv run ruff format src/ tests/

dev:
	cd web && npm run dev

# yagni: Makefile targets, create scripts/ when logic grows
export-tiles:
	cd pipeline && uv run python -m urbanstack.cli export --metro dfw
	cd pipeline && uv run python -m urbanstack.cli export --metro chicago
	cd pipeline && uv run python -m urbanstack.cli export --metro nyc

upload-r2:
	@for f in pipeline/exports/*.pmtiles; do \
		echo "Uploading $$(basename $$f)..."; \
		wrangler r2 object put "urbanstack/$$(basename $$f)" --file "$$f"; \
	done

clean:
	rm -rf data/raw/* data/staging/* data/marts/*
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
