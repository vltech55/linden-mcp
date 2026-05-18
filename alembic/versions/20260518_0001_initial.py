"""initial: read-only role, sample tables, pgvector documents

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-18 00:00:00
"""
from __future__ import annotations

from collections.abc import Sequence
from urllib.parse import urlparse

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

from mcp_server.core.config import settings


def _db_name() -> str:
    """Extract just the database name from DATABASE_URL.

    `urllib.parse.urlparse` cleanly drops the scheme, credentials, host, and
    query string; we only want the path component. The previous version used
    `rsplit('/', 1)[-1]` which silently included any `?sslmode=require`-style
    query suffix, producing invalid GRANT statements when the DSN had params.
    """
    path = urlparse(settings.database_url).path
    return path.lstrip("/").split("?", 1)[0]

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Create the read-only role idempotently. Password is set from settings so devs
    # can rotate it via env without editing migrations.
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{settings.readonly_user}') THEN
                CREATE ROLE {settings.readonly_user} WITH LOGIN PASSWORD '{settings.readonly_password}';
            END IF;
        END
        $$;
        """
    )

    op.create_table(
        "customers",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("email", sa.String(200), nullable=False, unique=True),
        sa.Column("country", sa.String(2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "orders",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "customer_id",
            sa.Uuid(),
            sa.ForeignKey("customers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sku", sa.String(64), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("placed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_orders_customer_id", "orders", ["customer_id"])

    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(settings.embedding_dim), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_documents_embedding_hnsw",
        "documents",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )

    # Grant SELECT-only on these tables; the role has no INSERT/UPDATE/DELETE/DDL by default.
    op.execute(f"GRANT CONNECT ON DATABASE {_db_name()} TO {settings.readonly_user}")
    op.execute(f"GRANT USAGE ON SCHEMA public TO {settings.readonly_user}")
    op.execute(f"GRANT SELECT ON ALL TABLES IN SCHEMA public TO {settings.readonly_user}")
    op.execute(
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO {settings.readonly_user}"
    )


def downgrade() -> None:
    op.execute(f"REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {settings.readonly_user}")
    op.drop_index("ix_documents_embedding_hnsw", table_name="documents")
    op.drop_table("documents")
    op.drop_index("ix_orders_customer_id", table_name="orders")
    op.drop_table("orders")
    op.drop_table("customers")
    op.execute(f"DROP ROLE IF EXISTS {settings.readonly_user}")
    op.execute("DROP EXTENSION IF EXISTS vector")
