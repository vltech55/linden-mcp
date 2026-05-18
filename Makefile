.PHONY: help up down logs build rebuild migrate seed test lint format psql stdio clean

help:
	@echo "Targets:"
	@echo "  up        start postgres + http transport"
	@echo "  migrate   apply alembic migrations (creates read-only role)"
	@echo "  seed      seed sample tables and documents"
	@echo "  stdio     run the MCP server in stdio mode (for piping to a client)"
	@echo "  test      run pytest suite"
	@echo "  lint      ruff + mypy"
	@echo "  format    ruff format + autofix"
	@echo "  psql      open psql shell"
	@echo "  down      stop containers"
	@echo "  clean     drop volumes (destructive)"

up:
	docker compose up -d
	@echo "HTTP transport: http://localhost:8765"

down:
	docker compose down

logs:
	docker compose logs -f --tail=200

build:
	docker compose build

rebuild:
	docker compose build --no-cache

migrate:
	docker compose exec mcp-http alembic upgrade head

seed:
	docker compose exec mcp-http python -m scripts.seed_db

stdio:
	docker compose exec mcp-http python -m mcp_server.server

test:
	docker compose exec mcp-http pytest -v

lint:
	docker compose exec mcp-http ruff check src tests scripts
	docker compose exec mcp-http mypy src

format:
	docker compose exec mcp-http ruff format src tests scripts
	docker compose exec mcp-http ruff check --fix src tests scripts

psql:
	docker compose exec postgres psql -U postgres -d mcp

clean:
	docker compose down -v
