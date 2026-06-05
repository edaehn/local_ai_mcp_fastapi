"""Tests for semantic_core. Run: pytest tests/test_semantic_core.py -v"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

import semantic_core as S


def test_cosine_similarity_identical_vectors():
    v = [1.0, 2.0, 3.0]
    assert S._cosine_similarity(v, v) == pytest.approx(1.0)


def test_cosine_similarity_orthogonal_vectors():
    assert S._cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_cosine_similarity_zero_vector_returns_zero():
    assert S._cosine_similarity([0.0, 0.0], [1.0, 2.0]) == 0.0


def test_excerpt_skips_markdown_headings():
    assert S._first_meaningful_line("# Title\n## Sub\nActual content") == "Actual content"


def test_load_cache_returns_empty_for_corrupt_file(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("not valid json", encoding="utf-8")
    assert S._load_cache(bad) == {}


def test_embed_returns_cached_value_without_calling_ollama():
    cache = {"mykey": [1.0, 2.0, 3.0]}
    assert S._embed("any text", cache, "mykey") == [1.0, 2.0, 3.0]


def test_embed_calls_ollama_on_cache_miss_and_stores_result():
    cache: dict = {}
    with patch(
        "semantic_core._ollama_embeddings",
        return_value={"embedding": [0.5, 0.5]},
    ) as mock_emb:
        result = S._embed("hello world", cache, "newkey")

    assert result == [0.5, 0.5]
    assert cache["newkey"] == [0.5, 0.5]
    mock_emb.assert_called_once_with(S.EMBED_MODEL, "hello world")


def test_embed_truncates_long_text_before_ollama():
    cache: dict = {}
    long_text = "x" * (S.MAX_CHARS_FOR_EMBED + 5000)
    with patch(
        "semantic_core._ollama_embeddings",
        return_value={"embedding": [1.0, 0.0]},
    ) as mock_emb:
        S._embed(long_text, cache, "longkey")

    _model, payload = mock_emb.call_args[0]
    assert _model == S.EMBED_MODEL
    assert len(payload) == S.MAX_CHARS_FOR_EMBED
    assert payload == "x" * S.MAX_CHARS_FOR_EMBED


def _write_files(directory: Path, files: dict[str, str]) -> None:
    for name, content in files.items():
        (directory / name).write_text(content, encoding="utf-8")


def _fake_embeddings(mapping: dict[str, list[float]]):
    def _inner(model, prompt):
        return {"embedding": mapping.get(prompt, [0.0, 0.0, 0.0])}

    return _inner


def test_find_similar_files_raises_for_invalid_directory():
    with pytest.raises(ValueError, match="Not a directory"):
        S.find_similar_files("query", directory="/no/such/path/xyz")


def test_find_similar_files_ranks_by_semantic_similarity(tmp_path):
    _write_files(
        tmp_path,
        {
            "caching.md": "caching strategies for expensive database queries",
            "css.md": "CSS grid layout and flexbox techniques",
            "indexing.md": "database indexing and query performance",
        },
    )
    embeddings = {
        "caching strategies for expensive database queries": [1.0, 0.0, 0.0],
        "CSS grid layout and flexbox techniques": [0.0, 0.0, 1.0],
        "database indexing and query performance": [0.8, 0.2, 0.0],
        "flask query optimisation": [0.9, 0.1, 0.0],
    }
    with patch("semantic_core._ollama_embeddings", side_effect=_fake_embeddings(embeddings)):
        results = S.find_similar_files(
            "flask query optimisation",
            directory=str(tmp_path),
            top_n=2,
            cache_file=tmp_path / "cache.json",
        )

    assert len(results) == 2
    assert results[0]["file"] == "caching.md"
    assert results[0]["score"] > results[1]["score"]
