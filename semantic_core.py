"""
Semantic file search using local Ollama embeddings (nomic-embed-text).

Used by the FastAPI + MCP server. Ollama is loaded only inside ``_ollama_embeddings``,
so importing this module does not require the ``ollama`` PyPI package (useful for
CI and for tests that patch ``_ollama_embeddings``).
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

EMBED_MODEL = "nomic-embed-text"
# Ollama embedding models enforce a max token length; long posts exceed it and return 500.
# Only the prefix is embedded; ranking still works for “where in the doc is the signal” demos.
MAX_CHARS_FOR_EMBED = 5_000
TEXT_EXTENSIONS = frozenset({".md", ".txt", ".rst", ".adoc"})
DEFAULT_CACHE = Path(".mcp_embed_cache.json")


def _clip_for_embedding(text: str) -> str:
    """Return a prefix of ``text`` safe for the embedding model context window."""
    if len(text) <= MAX_CHARS_FOR_EMBED:
        return text
    return text[:MAX_CHARS_FOR_EMBED]


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two vectors. Returns 0.0 for zero vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _first_meaningful_line(text: str, max_chars: int = 120) -> str:
    """Return the first non-empty, non-heading line as a preview excerpt."""
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        return stripped[:max_chars]
    return text.strip()[:max_chars]


def _load_cache(cache_file: Path) -> dict[str, list[float]]:
    if cache_file.exists():
        try:
            return json.loads(cache_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_cache(cache: dict[str, list[float]], cache_file: Path) -> None:
    cache_file.write_text(json.dumps(cache), encoding="utf-8")


def _ollama_embeddings(model: str, prompt: str) -> dict:
    """Call Ollama embedding API. Patched in unit tests."""
    import ollama

    return ollama.embeddings(model=model, prompt=prompt)


def _embed(text: str, cache: dict[str, list[float]], key: str) -> list[float]:
    """Return an embedding from cache, or compute it via Ollama and store it."""
    if key in cache:
        return cache[key]
    payload = _clip_for_embedding(text)
    response = _ollama_embeddings(EMBED_MODEL, payload)
    cache[key] = response["embedding"]
    return cache[key]


@dataclass
class _Entry:
    relative_path: str
    embedding: list[float]
    excerpt: str


def find_similar_files(
    query: str,
    directory: str = ".",
    top_n: int = 5,
    cache_file: Path | None = None,
) -> list[dict]:
    """
    Find text and Markdown files in ``directory`` most semantically similar to ``query``.

    Uses Ollama's ``nomic-embed-text`` model. Embeddings are cached by file path and
    modification time. Very long files are **truncated** to the first ``MAX_CHARS_FOR_EMBED``
    characters for embedding only (full file is still used for the excerpt line).

    Returns up to ``top_n`` dicts with keys: ``file``, ``score``, ``excerpt``.
    """
    root = Path(directory).resolve()
    if not root.is_dir():
        raise ValueError(f"Not a directory: {directory}")

    effective_cache = cache_file if cache_file is not None else (root / ".mcp_embed_cache.json")

    files = sorted(
        p for p in root.rglob("*")
        if p.is_file() and p.suffix.lower() in TEXT_EXTENSIONS
    )
    if not files:
        return []

    cache = _load_cache(effective_cache)
    entries: list[_Entry] = []

    for path in files:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore").strip()
        except OSError:
            continue
        if not text:
            continue
        key = f"{path}::{path.stat().st_mtime}"
        entries.append(
            _Entry(
                relative_path=str(path.relative_to(root)),
                embedding=_embed(text, cache, key),
                excerpt=_first_meaningful_line(text),
            )
        )

    if not entries:
        return []

    query_embedding = _embed(query, cache, f"__query__::{query}")
    _save_cache(cache, effective_cache)

    scored = sorted(
        ((e, _cosine_similarity(e.embedding, query_embedding)) for e in entries),
        key=lambda x: x[1],
        reverse=True,
    )

    return [
        {"file": e.relative_path, "score": round(score, 4), "excerpt": e.excerpt}
        for e, score in scored[:top_n]
    ]
