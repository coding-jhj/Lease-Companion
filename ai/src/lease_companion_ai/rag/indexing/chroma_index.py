"""공식자료 청크용 Chroma 로컬 벡터 인덱스."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

from lease_companion_ai.providers.embeddings import EmbeddingProvider, validate_embeddings
from lease_companion_ai.providers.errors import ProviderError
from lease_companion_ai.rag.models import (
    EvidenceQuery,
    RagChunk,
    RetrievalHit,
    query_to_search_text,
)


DEFAULT_COLLECTION_NAME = "lease_companion_official"
DEFAULT_CHUNKING_VERSION = "paragraph-section-v2-1200-120"


class StaleIndexError(RuntimeError):
    """저장된 인덱스와 현재 source·설정 fingerprint가 다름."""


def build_index_fingerprint(
    chunks: Sequence[RagChunk],
    *,
    chunking_version: str,
    embedding_model: str,
) -> str:
    if not chunks:
        raise ValueError("인덱스 fingerprint에는 청크가 1개 이상 필요합니다.")
    payload = {
        "chunk_ids": sorted(chunk.chunk_id for chunk in chunks),
        "source_hashes": sorted(
            {chunk.metadata.source_sha256 for chunk in chunks}
        ),
        "chunking_version": chunking_version,
        "embedding_model": embedding_model,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


class ChromaVectorIndex:
    """외부 embedding provider와 Chroma 저장소를 조합한다."""

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        *,
        persist_path: Path | str | None = None,
        client: Any | None = None,
        collection_name: str = DEFAULT_COLLECTION_NAME,
        chunking_version: str = DEFAULT_CHUNKING_VERSION,
    ) -> None:
        if client is not None and persist_path is not None:
            raise ValueError("client와 persist_path는 동시에 지정할 수 없습니다.")
        if client is None:
            import chromadb

            client = (
                chromadb.PersistentClient(path=Path(persist_path))
                if persist_path is not None
                else chromadb.EphemeralClient()
            )
        self._client = client
        self._provider = embedding_provider
        self._collection_name = collection_name
        self._chunking_version = chunking_version

    def close(self) -> None:
        """Persistent client 파일 핸들을 명시적으로 닫는다."""
        close = getattr(self._client, "close", None)
        if callable(close):
            close()

    def index_chunks(
        self,
        chunks: Sequence[RagChunk],
        *,
        rebuild: bool = False,
    ) -> str:
        if not chunks:
            raise ValueError("Chroma 인덱스에는 청크가 1개 이상 필요합니다.")
        chunk_ids = [chunk.chunk_id for chunk in chunks]
        if len(chunk_ids) != len(set(chunk_ids)):
            raise ValueError("Chroma 인덱스에 중복 chunk_id가 있습니다.")
        fingerprint = build_index_fingerprint(
            chunks,
            chunking_version=self._chunking_version,
            embedding_model=self._provider.model_name,
        )
        metadata = {
            "index_fingerprint": fingerprint,
            "chunking_version": self._chunking_version,
            "embedding_model": self._provider.model_name,
        }
        collection_names = {collection.name for collection in self._client.list_collections()}
        if rebuild and self._collection_name in collection_names:
            self._client.delete_collection(name=self._collection_name)
        collection = self._client.get_or_create_collection(
            name=self._collection_name,
            metadata=metadata,
        )
        existing_fingerprint = (collection.metadata or {}).get("index_fingerprint")
        if collection.count() and existing_fingerprint != fingerprint:
            raise StaleIndexError("저장된 Chroma 인덱스는 재색인이 필요합니다.")
        if collection.count() == len(chunks) and existing_fingerprint == fingerprint:
            return fingerprint
        if not collection.count() and existing_fingerprint != fingerprint:
            collection.modify(metadata=metadata)

        embeddings = validate_embeddings(
            self._provider.embed_documents([chunk.text for chunk in chunks]),
            expected_count=len(chunks),
        )
        chroma_embeddings = cast(
            list[Sequence[float] | Sequence[int]],
            embeddings,
        )
        collection.upsert(
            ids=chunk_ids,
            embeddings=chroma_embeddings,
            documents=[chunk.text for chunk in chunks],
            metadatas=[{"rag_chunk_json": chunk.model_dump_json()} for chunk in chunks],
        )
        return fingerprint

    def search(
        self,
        query: EvidenceQuery | str,
        *,
        top_k: int = 20,
    ) -> list[RetrievalHit]:
        if top_k <= 0:
            raise ValueError("top_k는 양수여야 합니다.")
        try:
            collection = self._client.get_collection(name=self._collection_name)
            collection_count = collection.count()
            if collection_count == 0:
                return []
            query_text = query_to_search_text(query)
            embedding = validate_embeddings(
                [self._provider.embed_query(query_text)],
                expected_count=1,
            )[0]
            query_embeddings = cast(
                list[Sequence[float] | Sequence[int]],
                [embedding],
            )
            result = collection.query(
                query_embeddings=query_embeddings,
                n_results=min(top_k, collection_count),
                include=["metadatas", "distances"],
            )
            metadatas = (result.get("metadatas") or [[]])[0]
            distances = (result.get("distances") or [[]])[0]
            candidates: list[tuple[float, RagChunk]] = []
            for metadata, distance in zip(metadatas, distances, strict=True):
                if metadata is None or distance is None:
                    continue
                chunk = RagChunk.model_validate_json(metadata["rag_chunk_json"])
                score = 1.0 / (1.0 + max(float(distance), 0.0))
                candidates.append((score, chunk))
        except ProviderError:
            raise
        except Exception:
            raise ProviderError("Chroma vector 검색에 실패했습니다.") from None
        ranked = sorted(candidates, key=lambda item: (-item[0], item[1].chunk_id))
        return [
            RetrievalHit(
                chunk=chunk,
                score=score,
                rank=rank,
                retrieval_method="vector",
            )
            for rank, (score, chunk) in enumerate(ranked, start=1)
        ]
