from __future__ import annotations

import tempfile
from collections.abc import Sequence
from pathlib import Path

import chromadb
import pytest

from lease_companion_ai.rag.indexing.chroma_index import ChromaVectorIndex, StaleIndexError
from lease_companion_ai.rag.indexing.chunker import chunk_sections


class FakeEmbeddingProvider:
    model_name = "fake-embedding-v1"

    @staticmethod
    def _embed(text: str) -> list[float]:
        return [float(text.count("소유자")), float(text.count("근저당권")), 1.0]

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


def _chunks(source_metadata):
    return chunk_sections(
        source_metadata,
        [("소유권", "임대인과 등기상 소유자를 확인"), ("담보권", "근저당권 채권최고액 확인")],
    )


def test_chroma_index_is_idempotent_and_searchable(source_metadata):
    client = chromadb.EphemeralClient()
    index = ChromaVectorIndex(
        FakeEmbeddingProvider(), client=client, collection_name="test_idempotent"
    )
    chunks = _chunks(source_metadata)

    first = index.index_chunks(chunks)
    second = index.index_chunks(chunks)
    hits = index.search("근저당권", top_k=2)

    assert first == second
    assert client.get_collection("test_idempotent").count() == 2
    assert hits[0].chunk.section == "담보권"
    assert all(hit.retrieval_method == "vector" for hit in hits)


def test_chroma_index_detects_stale_chunking_config(source_metadata):
    client = chromadb.EphemeralClient()
    chunks = _chunks(source_metadata)
    ChromaVectorIndex(
        FakeEmbeddingProvider(),
        client=client,
        collection_name="test_stale",
        chunking_version="chunk-v1",
    ).index_chunks(chunks)

    with pytest.raises(StaleIndexError, match="재색인"):
        ChromaVectorIndex(
            FakeEmbeddingProvider(),
            client=client,
            collection_name="test_stale",
            chunking_version="chunk-v2",
        ).index_chunks(chunks)

    replacement = ChromaVectorIndex(
        FakeEmbeddingProvider(),
        client=client,
        collection_name="test_stale",
        chunking_version="chunk-v2",
    )
    replacement.index_chunks(chunks, rebuild=True)
    collection = client.get_collection("test_stale")
    assert collection.count() == len(chunks)
    assert collection.metadata["chunking_version"] == "chunk-v2"


def test_chroma_persistent_index_reopens(source_metadata):
    index_root = Path(__file__).resolve().parents[3] / "data" / "rag" / "index"
    index_root.mkdir(parents=True, exist_ok=True)
    chunks = _chunks(source_metadata)
    with tempfile.TemporaryDirectory(dir=index_root) as temp_directory:
        persist_path = Path(temp_directory) / "chroma"
        initial = ChromaVectorIndex(
            FakeEmbeddingProvider(),
            persist_path=persist_path,
            collection_name="test_persistent",
        )
        initial.index_chunks(chunks)
        initial.close()

        reopened = ChromaVectorIndex(
            FakeEmbeddingProvider(),
            persist_path=persist_path,
            collection_name="test_persistent",
        )

        assert reopened.search("소유자", top_k=1)[0].chunk.section == "소유권"
        reopened.close()
