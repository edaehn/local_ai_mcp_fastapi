"""Shared MCP tool definitions for ``main.py`` (HTTP) and ``mcp_server.py`` (stdio)."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

import semantic_core


def attach_semantic_search_tools(mcp: FastMCP) -> None:
    """Register ``find_similar_files`` on the given FastMCP instance."""

    @mcp.tool()
    def find_similar_files(
        query: str,
        directory: str = ".",
        top_n: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Rank Markdown and plain-text files under ``directory`` (recursive) by semantic similarity to ``query``.

        File types: .md, .txt, .rst, .adoc. Uses Ollama ``nomic-embed-text`` embeddings and cosine similarity.
        Returns list of dicts with keys ``file`` (relative path), ``score``, ``excerpt``. ``directory`` must be
        readable by the server; keep ``top_n`` between 1 and 50.
        """
        return semantic_core.find_similar_files(query, directory=directory, top_n=top_n)
