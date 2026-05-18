from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from mcp_server.core.config import settings


class Base(DeclarativeBase):
    pass


admin_engine: AsyncEngine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=5,
    future=True,
)

# Separate pool for the sandboxed SQL tool. This engine connects as the
# read-only role created by migrations, so even a connection-level escape
# can't write data.
readonly_engine: AsyncEngine = create_async_engine(
    settings.readonly_database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=5,
    future=True,
    connect_args={
        "server_settings": {
            "default_transaction_read_only": "on",
            "statement_timeout": str(settings.sql_statement_timeout_ms),
        }
    },
)

AdminSession = async_sessionmaker(bind=admin_engine, expire_on_commit=False, class_=AsyncSession)
