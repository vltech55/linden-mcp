"""Seed customers, orders, and indexed documents into the MCP server's database.

Idempotent: re-running clears the rows in the same transaction. Run after migrations.
"""
from __future__ import annotations

import asyncio
import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from openai import AsyncOpenAI
from sqlalchemy import delete, text

from mcp_server.core.config import settings
from mcp_server.core.logging import configure_logging, get_logger
from mcp_server.db import AdminSession
from mcp_server.models import Customer, Document, Order

random.seed(42)
log = get_logger("seed")


_CUSTOMERS = [
    ("Alice Becker", "alice@example.com", "DE"),
    ("Bao Nguyen", "bao@example.com", "VN"),
    ("Carla Rossi", "carla@example.com", "IT"),
    ("Diego Hernandez", "diego@example.com", "MX"),
    ("Esi Mensah", "esi@example.com", "GH"),
    ("Farah El-Sayed", "farah@example.com", "EG"),
    ("Gustav Linström", "gustav@example.com", "SE"),
    ("Hina Sato", "hina@example.com", "JP"),
]

_SKUS = ["LAPTOP-13", "LAPTOP-15", "MOUSE-OPT", "KEYBOARD-MX", "MONITOR-27", "DOCK-USB-C", "WEBCAM-1080"]
_STATUSES = ["pending", "paid", "shipped", "delivered", "refunded"]


_DOCS = [
    {
        "title": "Model Context Protocol — Overview",
        "url": "https://example.com/mcp-overview",
        "content": (
            "The Model Context Protocol (MCP) is a JSON-RPC-based standard for "
            "exposing tools, resources, and prompts to LLM clients. Servers run "
            "over stdio for desktop clients or over HTTP/SSE for remote use, and "
            "the same tool definitions can be used by both transports."
        ),
    },
    {
        "title": "Securing SQL Tools for LLM Agents",
        "url": "https://example.com/sql-safety",
        "content": (
            "Exposing arbitrary SQL to an LLM is dangerous. Production patterns: "
            "use a dedicated read-only Postgres role, set a statement_timeout, "
            "enforce default_transaction_read_only at the session, parse incoming "
            "queries with a SQL AST and reject anything other than SELECT or CTE, "
            "and append LIMIT clauses automatically."
        ),
    },
    {
        "title": "Token-Bucket Rate Limiting",
        "url": "https://example.com/token-bucket",
        "content": (
            "A token bucket has two parameters: capacity and refill rate. Tokens "
            "accumulate up to capacity at the refill rate. A request consumes a "
            "token; if none are available the request is rejected with HTTP 429 "
            "and a Retry-After header. Simple to implement in-memory for a single "
            "process; swap the backing store for Redis to scale horizontally."
        ),
    },
    {
        "title": "Open-Meteo: Free Weather Data",
        "url": "https://example.com/open-meteo",
        "content": (
            "Open-Meteo is a free, no-key weather API providing current conditions, "
            "hourly and daily forecasts worldwide. Suitable for portfolio demos and "
            "production read-side workloads with attribution."
        ),
    },
    {
        "title": "pgvector HNSW vs IVFFlat",
        "url": "https://example.com/pgvector-hnsw",
        "content": (
            "HNSW gives better recall at low latency for corpora up to ~10M vectors. "
            "Build parameters m=16 and ef_construction=64 are reasonable defaults. "
            "Trade-off: ~2x the index size of IVFFlat for equivalent recall."
        ),
    },
]


async def seed() -> None:
    configure_logging()
    client = AsyncOpenAI(api_key=settings.openai_api_key)

    async with AdminSession() as session:
        await session.execute(delete(Order))
        await session.execute(delete(Customer))
        await session.execute(delete(Document))
        await session.commit()

        customers: list[Customer] = []
        for name, email, country in _CUSTOMERS:
            c = Customer(name=name, email=email, country=country)
            session.add(c)
            customers.append(c)
        await session.flush()

        for c in customers:
            for _ in range(random.randint(1, 4)):
                session.add(
                    Order(
                        customer_id=c.id,
                        sku=random.choice(_SKUS),
                        quantity=random.randint(1, 5),
                        unit_price=Decimal(random.choice(["19.99", "59.00", "129.50", "299.00", "549.00"])),
                        status=random.choice(_STATUSES),
                        placed_at=datetime.now(timezone.utc) - timedelta(days=random.randint(0, 90)),
                    )
                )

        if not settings.openai_api_key:
            log.warning("openai_key_missing_skipping_docs")
        else:
            texts = [d["content"] for d in _DOCS]
            resp = await client.embeddings.create(
                model=settings.openai_embedding_model,
                input=texts,
            )
            for d, emb in zip(_DOCS, resp.data, strict=True):
                session.add(
                    Document(
                        title=d["title"],
                        url=d["url"],
                        content=d["content"],
                        embedding=emb.embedding,
                    )
                )

        await session.commit()

    async with AdminSession() as s:
        counts = (
            (await s.execute(text("SELECT count(*) FROM customers"))).scalar_one(),
            (await s.execute(text("SELECT count(*) FROM orders"))).scalar_one(),
            (await s.execute(text("SELECT count(*) FROM documents"))).scalar_one(),
        )
        log.info("seeded", customers=counts[0], orders=counts[1], documents=counts[2])


if __name__ == "__main__":
    asyncio.run(seed())
