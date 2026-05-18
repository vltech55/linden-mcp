# Wiring this MCP server into Claude Desktop

Claude Desktop reads its MCP servers from a JSON config file:

| OS      | Path                                                                  |
| ------- | --------------------------------------------------------------------- |
| macOS   | `~/Library/Application Support/Claude/claude_desktop_config.json`     |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json`                         |
| Linux   | `~/.config/Claude/claude_desktop_config.json`                         |

## 1. Boot the server

```bash
cd 03-mcp-server
cp .env.example .env
# Set OPENAI_API_KEY in .env (used by search_documents for embeddings).
make up
make migrate
make seed
```

## 2. Point Claude Desktop at it

Copy `claude_desktop_config.example.json` into the config path above, replacing
`/ABSOLUTE/PATH/TO/` with your real path to this repo. The relevant fragment:

```json
{
  "mcpServers": {
    "portfolio-mcp": {
      "command": "docker",
      "args": [
        "compose", "-f", "/ABSOLUTE/PATH/TO/03-mcp-server/docker-compose.yml",
        "exec", "-T", "mcp-http",
        "python", "-m", "mcp_server.server"
      ]
    }
  }
}
```

Restart Claude Desktop. You should see "portfolio-mcp" in the tools menu with
five tools: `sql_query`, `list_tables`, `weather_current`, `weather_forecast`,
`search_documents`.

## 3. Try it in conversation

> "Use list_tables to see what's in the database, then show me the top
> three customers by total order value."

Claude will call `list_tables`, then issue a single `sql_query` JOIN. Any
attempt to write data — even via a CTE — is rejected before reaching Postgres.

## Alternative: HTTP transport (no Desktop required)

The same tools are exposed over FastAPI on port 8765 with API-key auth and
per-key rate limiting. Useful for testing, browser clients, or integrations
that can't run stdio.

```bash
curl -X POST http://localhost:8765/tools/sql_query \
  -H "Content-Type: application/json" \
  -H "X-API-Key: demo-key-please-rotate" \
  -d '{"query": "SELECT COUNT(*) FROM customers"}'
```
