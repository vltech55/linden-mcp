# MCP Server: Database, Weather & Semantic Search Tools

A production-pattern [Model Context Protocol](https://modelcontextprotocol.io)
server exposing three tool categories to LLM clients: sandboxed PostgreSQL
queries, weather data via Open-Meteo, and pgvector semantic search over a
document store. Implements the MCP spec via the official Python SDK and
ships both **stdio** (Claude Desktop) and **HTTP/SSE** (remote auth +
rate-limited) transports from one tool surface.

> **Why this exists:** MCP is the emerging standard for giving LLMs
> structured, secure access to external systems. Most teams have never
> built a real one. This project shows what the production patterns look
> like — strict tool schemas, layered SQL safety, API-key auth, token-bucket
> rate limiting, structured logging — and is configured to drop into Claude
> Desktop with a single config edit.

---

## Tools

| Tool                | Input                                | Returns                                   |
| ------------------- | ------------------------------------ | ----------------------------------------- |
| `sql_query`         | `{query: str, limit: int}`           | rows + count + truncated + latency        |
| `list_tables`       | `{}`                                 | tables visible to the read-only role      |
| `weather_current`   | `{latitude, longitude}`              | temp, humidity, wind, weather code        |
| `weather_forecast`  | `{latitude, longitude, days}`        | daily min/max + precipitation + code      |
| `search_documents`  | `{query: str, top_k: int}`           | top-k document hits with cosine similarity|

All five tools share strict Pydantic input schemas exposed via the MCP
`inputSchema` field, so clients (and the LLM) see the exact types and
ranges before calling.

## Layered SQL safety

The `sql_query` tool can be exposed to an untrusted LLM safely because the
sandbox stacks four independent defenses:

1. **Token guard** — regex rejects `INSERT/UPDATE/DELETE/DROP/ALTER/CREATE/TRUNCATE/GRANT/REVOKE/...` even inside CTEs.
2. **AST parse** — `sqlglot` rejects anything that isn't a SELECT/UNION/WITH-of-SELECT, and rejects multiple statements.
3. **Auto-LIMIT** — appends `LIMIT 100` (configurable cap) if absent; clamps oversized LIMITs.
4. **Read-only role** — a dedicated `mcp_readonly` Postgres role with `GRANT SELECT` only, `default_transaction_read_only=on`, and a `statement_timeout=5s`. Even bypassing every check above, the database itself refuses to write.

Tests verify each layer independently.

## Stack

- **Protocol:** `mcp` Python SDK (stdio + HTTP transports)
- **HTTP wrapper:** FastAPI with API-key auth (`hmac.compare_digest`) and per-key token-bucket rate limiting
- **DB:** PostgreSQL 16 + pgvector; two engines (admin for migrations, read-only for tools)
- **Embeddings:** OpenAI `text-embedding-3-small` (1536-dim, HNSW index)
- **Weather:** Open-Meteo (free, no key)
- **SQL parsing:** `sqlglot`
- **Reliability:** `tenacity` retries on external calls, structured logging via `structlog`
- **Migrations:** Alembic; idempotent role + grants

## Quick start

```bash
cp .env.example .env
# Set OPENAI_API_KEY (used by search_documents for embeddings).
make up
make migrate     # creates the mcp_readonly role + grants + extension + tables
make seed        # populates 8 customers, ~20 orders, 5 indexed documents

# Demo the stdio transport using the bundled MCP client:
docker compose exec mcp-http python -m scripts.client_demo
```

Hooking into Claude Desktop: see [`docs/claude-desktop.md`](./docs/claude-desktop.md).

## HTTP transport

The same tools also live behind a FastAPI surface on port 8765 with API-key auth and per-key rate limiting:

```bash
curl -X POST http://localhost:8765/tools/sql_query \
  -H "Content-Type: application/json" \
  -H "X-API-Key: demo-key-please-rotate" \
  -d '{"query": "SELECT name, country FROM customers", "limit": 5}'
```

Endpoints: `/health`, `/tools`, `/tools/{tool_name}` (POST). Auth dependency
runs first; rate-limit dependency consumes a token keyed by the API key on
success. 401 on bad auth, 429 on rate-limit with `Retry-After` header.

## Project layout

```
03-mcp-server/
├── src/mcp_server/
│   ├── core/
│   │   ├── auth.py         API-key dependency (constant-time compare)
│   │   ├── ratelimit.py    in-memory token bucket per API key
│   │   ├── sql_sandbox.py  4-layer SQL safety
│   │   ├── config.py
│   │   └── logging.py
│   ├── tools/
│   │   ├── sql.py          sql_query, list_tables
│   │   ├── weather.py      Open-Meteo wrapper
│   │   └── search.py       embed + pgvector top-k
│   ├── db.py               admin + read-only engines
│   ├── models.py           customers, orders, documents
│   ├── schemas.py          Pydantic tool I/O
│   ├── server.py           MCP stdio entrypoint
│   └── http_server.py      FastAPI HTTP transport
├── alembic/                migration creates role + grants + pgvector + tables
├── scripts/
│   ├── seed_db.py          deterministic seed data
│   └── client_demo.py      stdio MCP client that exercises every tool
├── tests/                  sandbox, rate limit, auth, schemas
├── docs/                   architecture + claude-desktop walkthrough
├── claude_desktop_config.example.json
├── docker-compose.yml
├── Dockerfile
├── Makefile
└── .env.example
```

## Make targets

```
make up         postgres + http transport (port 8765)
make migrate    alembic upgrade head
make seed       populate sample tables + indexed documents
make stdio      run the MCP server in stdio mode (rare; usually Desktop spawns it)
make test       pytest (sandbox, rate limit, auth, schemas)
make lint       ruff + mypy strict
make psql       open psql shell
```

## What this isn't (yet)

- Distributed rate limiting — current limiter is in-process. Swap to Redis for horizontal scale.
- API-key rotation UI — keys live in `.env`; production would back this by a secrets manager.
- OAuth — the brief calls for API keys; OAuth is a separate spec MCP also supports.

## License

MIT.
