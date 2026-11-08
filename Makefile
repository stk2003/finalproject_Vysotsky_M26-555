.PHONY: install run lint format build

install:
	uv sync

run:
	uv run --no-editable valutatrade-hub

lint:
	uv run ruff check .

format:
	uv run ruff format .

build:
	uv build
