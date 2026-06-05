"""
FastAPI app exposing:

- ``GET /health`` — liveness for ops and sanity checks
- ``POST /api/search`` — optional JSON REST wrapper around semantic search (no MCP client required)
- ``/mcp`` — MCP **Streamable HTTP** (recommended for Claude Code: ``--transport http``)
- ``/mcp-sse`` — MCP legacy **SSE** transport (useful with ``mcp-remote`` for Claude Desktop)

For **stdio** MCP (Cline, Claude Desktop without HTTP), use ``mcp_server.py`` in this folder instead.

Run::

    uvicorn main:app --host 127.0.0.1 --port 8765

Requires Ollama with ``nomic-embed-text`` for embedding calls.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel

import semantic_core
from mcp_tools import attach_semantic_search_tools


def build_mcp() -> FastMCP:
    mcp = FastMCP(
        "local-doc-search",
        instructions=(
            "Local semantic search over Markdown and plain text using Ollama "
            "embeddings (model: nomic-embed-text). Ollama must be running on the host."
        ),
        stateless_http=True,
        streamable_http_path="/",
        mount_path="/mcp-sse",
        sse_path="/sse",
        message_path="/messages/",
    )
    attach_semantic_search_tools(mcp)
    return mcp


mcp = build_mcp()
streamable_asgi = mcp.streamable_http_app()
sse_asgi = mcp.sse_app()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Streamable HTTP session manager (shared); safe to enter even if you only use SSE.
    async with mcp.session_manager.run():
        yield


app = FastAPI(
    title="Local AI MCP (FastAPI)",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


class SearchBody(BaseModel):
    query: str
    directory: str = "."
    top_n: int = 5


@app.post("/api/search")
def search_rest(body: SearchBody) -> list[dict[str, Any]]:
    """Non-MCP JSON endpoint for quick manual tests (curl / HTTP client)."""
    return semantic_core.find_similar_files(
        body.query,
        directory=body.directory,
        top_n=body.top_n,
    )


# Streamable HTTP MCP: full URL http://127.0.0.1:8765/mcp
app.mount("/mcp", streamable_asgi)
# SSE MCP: GET http://127.0.0.1:8765/mcp-sse/sse , POST messages under /mcp-sse/messages/
app.mount("/mcp-sse", sse_asgi)
