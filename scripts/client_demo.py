"""Tiny MCP client that spawns the stdio server, lists tools, and calls each one.

Run inside the container:
    docker compose exec mcp-http python -m scripts.client_demo

The same script is what you'd record for the README's screen-recording artifact.
"""
from __future__ import annotations

import asyncio
import json
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main() -> None:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "mcp_server.server"],
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            print("\n=== Tools advertised by the server ===")  # noqa: T201
            for t in tools.tools:
                print(f"  {t.name}: {t.description.split('.')[0]}.")  # noqa: T201

            print("\n=== list_tables ===")  # noqa: T201
            r = await session.call_tool("list_tables", {})
            print(r.content[0].text)  # noqa: T201

            print("\n=== sql_query: top 3 customers by order count ===")  # noqa: T201
            r = await session.call_tool(
                "sql_query",
                {
                    "query": (
                        "SELECT c.name, COUNT(o.id) AS orders "
                        "FROM customers c JOIN orders o ON o.customer_id = c.id "
                        "GROUP BY c.name ORDER BY orders DESC"
                    ),
                    "limit": 3,
                },
            )
            print(json.dumps(json.loads(r.content[0].text), indent=2))  # noqa: T201

            print("\n=== sql_query: should be rejected (UPDATE) ===")  # noqa: T201
            r = await session.call_tool(
                "sql_query",
                {"query": "UPDATE customers SET name = 'pwned' WHERE 1=1"},
            )
            print(r.content[0].text)  # noqa: T201

            print("\n=== weather_current: Berlin ===")  # noqa: T201
            r = await session.call_tool("weather_current", {"latitude": 52.52, "longitude": 13.41})
            print(json.dumps(json.loads(r.content[0].text), indent=2))  # noqa: T201

            print("\n=== search_documents: 'how do I sandbox SQL' ===")  # noqa: T201
            r = await session.call_tool(
                "search_documents",
                {"query": "how do I sandbox SQL for an LLM tool", "top_k": 3},
            )
            print(json.dumps(json.loads(r.content[0].text), indent=2))  # noqa: T201


if __name__ == "__main__":
    asyncio.run(main())
