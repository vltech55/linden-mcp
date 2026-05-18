from __future__ import annotations

import os

os.environ.setdefault("OPENAI_API_KEY", "test")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/mcp_test")
os.environ.setdefault("READONLY_DATABASE_URL", "postgresql+asyncpg://mcp_readonly:mcp_readonly@localhost:5432/mcp_test")
os.environ.setdefault("MCP_API_KEYS", "test-key-1,test-key-2")
