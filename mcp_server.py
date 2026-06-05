#!/usr/bin/env python3
"""
Stdio MCP server — same ``find_similar_files`` tool as ``main.py``, no HTTP.

Your editor (Cline, Cursor, …) or Claude Desktop spawns this process and talks
MCP over stdin/stdout. No open port, no ``uvicorn``. Ollama must be running with
``nomic-embed-text`` pulled.

Run (for a quick manual check, from this directory)::

    python mcp_server.py

Configure Cline (or similar) with ``type: stdio`` and ``command``/``args`` pointing
at this file — see README.md.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from mcp_tools import attach_semantic_search_tools

STDIO_INSTRUCTIONS = (
    "Local semantic search over Markdown and plain text using Ollama "
    "embeddings (model: nomic-embed-text). Ollama must be running on the host. "
    "Stdio transport: launched by the MCP client as a subprocess."
)


def build_stdio_mcp() -> FastMCP:
    mcp = FastMCP("local-doc-search", instructions=STDIO_INSTRUCTIONS)
    attach_semantic_search_tools(mcp)
    return mcp


def main() -> None:
    mcp = build_stdio_mcp()
    mcp.run()


if __name__ == "__main__":
    main()
