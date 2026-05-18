from __future__ import annotations

from functools import lru_cache

from openai import AsyncOpenAI
from sqlalchemy import bindparam, text

from mcp_server.core.config import settings
from mcp_server.core.logging import get_logger
from mcp_server.db import readonly_engine
from mcp_server.schemas import DocumentHit, SearchDocsInput, SearchDocsResult

log = get_logger(__name__)


@lru_cache(maxsize=1)
def _openai() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=settings.openai_api_key)


async def _embed(text_in: str) -> list[float]:
    resp = await _openai().embeddings.create(
        model=settings.openai_embedding_model,
        input=text_in,
    )
    return resp.data[0].embedding


_SQL = text(
    """
    SELECT id, title, url, content, 1 - (embedding <=> CAST(:vec AS vector)) AS similarity
    FROM documents
    ORDER BY embedding <=> CAST(:vec AS vector)
    LIMIT :limit
    """
).bindparams(bindparam("vec"), bindparam("limit"))


def _vec_literal(v: list[float]) -> str:
    return "[" + ",".join(f"{x:.7f}" for x in v) + "]"


async def search_documents(params: SearchDocsInput) -> SearchDocsResult:
    """Embed the query and return the top-k closest documents by cosine similarity."""
    vec = await _embed(params.query)
    async with readonly_engine.begin() as conn:
        rows = (
            await conn.execute(_SQL, {"vec": _vec_literal(vec), "limit": params.top_k})
        ).mappings().all()

    hits = [
        DocumentHit(
            id=str(r["id"]),
            title=r["title"],
            url=r["url"],
            snippet=(r["content"] or "")[:400],
            similarity=float(r["similarity"]),
        )
        for r in rows
    ]
    log.info("search_documents", query=params.query[:80], hits=len(hits))
    return SearchDocsResult(query=params.query, hits=hits)
