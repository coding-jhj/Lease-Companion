"""규칙 결과를 변경하지 않고 실제 검색된 공식 근거만 연결한다."""

from __future__ import annotations

import json
import os
import csv
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol

from lease_companion_ai.providers.cohere_rerank import CohereRerankProvider
from lease_companion_ai.providers.embeddings import EmbeddingProvider
from lease_companion_ai.providers.errors import ProviderError
from lease_companion_ai.providers.gemini_embeddings import GeminiEmbeddingProvider
from lease_companion_ai.providers.rerank import RerankProvider
from lease_companion_ai.rag.indexing.chroma_index import (
    DEFAULT_CHUNKING_VERSION,
    DEFAULT_COLLECTION_NAME,
    ChromaVectorIndex,
    StaleIndexError,
)
from lease_companion_ai.rag.indexing.chunker import chunk_sections
from lease_companion_ai.rag.models import (
    EvidenceQuery,
    JudgmentRetrievalQuery,
    RagChunk,
    RagSourceMetadata,
    RetrievalHit,
    RetrievalQuery,
)
from lease_companion_ai.rag.reranking.service import RerankingService
from lease_companion_ai.rag.retrieval.bm25 import BM25Index
from lease_companion_ai.rag.retrieval.hybrid import HybridRetriever
from lease_companion_ai.schemas.unified import (
    AnalysisRunResult,
    JudgmentResult,
    OfficialSource,
    RuleResult,
)


class Retriever(Protocol):
    def search(
        self, query: EvidenceQuery | str, *, top_k: int = 20
    ) -> list[RetrievalHit]: ...


@dataclass(frozen=True, slots=True)
class EvidenceSearchResult:
    hits: tuple[RetrievalHit, ...]
    provider_fallback_used: bool = False


class EvidenceRetrievalService:
    def __init__(
        self,
        retriever: Retriever,
        reranker: RerankingService | None = None,
        *,
        judgment_source_ids: Mapping[str, tuple[str, ...]] | None = None,
    ) -> None:
        self._retriever = retriever
        self._reranker = reranker
        self._judgment_source_ids = dict(
            judgment_source_ids
            if judgment_source_ids is not None
            else load_judgment_source_ids()
        )

    def search(
        self,
        query: EvidenceQuery,
        *,
        top_k: int = 20,
        top_n: int = 5,
    ) -> EvidenceSearchResult:
        try:
            hits = self._retriever.search(query, top_k=top_k)
        except ProviderError:
            return EvidenceSearchResult((), provider_fallback_used=True)
        if isinstance(query, JudgmentRetrievalQuery):
            allowed = set(query.allowed_source_ids)
            hits = [
                hit for hit in hits if hit.chunk.metadata.source_id in allowed
            ]
            hits = [
                hit.model_copy(update={"rank": rank})
                for rank, hit in enumerate(hits, start=1)
            ]
        fallback = bool(hits) and all(hit.retrieval_method == "bm25" for hit in hits)
        if self._reranker is None:
            return EvidenceSearchResult(
                tuple(hits[:top_n]), provider_fallback_used=fallback
            )
        reranked = self._reranker.rerank(query, hits, top_n=top_n)
        if reranked and any(hit.retrieval_method != "rerank" for hit in reranked):
            fallback = True
        return EvidenceSearchResult(tuple(reranked), provider_fallback_used=fallback)

    def enrich(self, analysis: AnalysisRunResult) -> AnalysisRunResult:
        enriched: list[RuleResult] = []
        for result in analysis.results:
            evidence: list[OfficialSource] = []
            if result.triggers_actions:
                query = RetrievalQuery(
                    rule_id=result.rule_id,
                    rule_name=result.rule_name,
                    status=result.status,
                )
                search_result = self.search(query)
                seen: set[str] = set()
                for hit in search_result.hits:
                    metadata = hit.chunk.metadata
                    if metadata.source_id in seen:
                        continue
                    seen.add(metadata.source_id)
                    evidence.append(
                        OfficialSource(
                            source_id=metadata.source_id,
                            title=metadata.document_title,
                            institution=metadata.institution,
                            summary=hit.chunk.text[:500],
                            source_url=metadata.source_url,
                        )
                    )
            enriched.append(result.model_copy(update={"evidence_sources": evidence}))
        enriched_judgments: list[JudgmentResult] = []
        for judgment in analysis.judgments:
            judgment_evidence: list[OfficialSource] = []
            allowed_source_ids = self._judgment_source_ids.get(
                judgment.judgment_id, ()
            )
            if judgment.triggers_actions and allowed_source_ids:
                judgment_query = JudgmentRetrievalQuery(
                    judgment_id=judgment.judgment_id,
                    judgment_name=judgment.judgment_name,
                    status=judgment.status,
                    allowed_source_ids=allowed_source_ids,
                )
                search_result = self.search(judgment_query)
                judgment_seen: set[str] = set()
                for hit in search_result.hits:
                    metadata = hit.chunk.metadata
                    if metadata.source_id in judgment_seen:
                        continue
                    judgment_seen.add(metadata.source_id)
                    judgment_evidence.append(
                        OfficialSource(
                            source_id=metadata.source_id,
                            title=metadata.document_title,
                            institution=metadata.institution,
                            summary=hit.chunk.text[:500],
                            source_url=metadata.source_url,
                        )
                    )
            enriched_judgments.append(
                judgment.model_copy(update={"evidence_sources": judgment_evidence})
            )
        return AnalysisRunResult.model_validate(
            analysis.model_copy(
                update={"results": enriched, "judgments": enriched_judgments}
            ).model_dump()
        )


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def load_judgment_source_ids(root: Path | None = None) -> dict[str, tuple[str, ...]]:
    """J 명세의 판정별 공식자료 allowlist를 순서까지 보존해 읽는다."""
    repo_root = root or _repo_root()
    path = repo_root / "data" / "rules" / "judgment_spec.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    expected_ids = [f"J{index:02d}" for index in range(1, 13)]
    judgment_ids = [row["judgment_id"] for row in rows]
    if judgment_ids != expected_ids:
        raise ValueError("judgment_spec에는 J01~J12가 순서대로 있어야 합니다.")
    mapping: dict[str, tuple[str, ...]] = {}
    for row in rows:
        source_ids = tuple(
            source_id.strip()
            for source_id in row["official_source_ids"].split(";")
            if source_id.strip()
        )
        if not source_ids:
            raise ValueError(f"{row['judgment_id']} 공식자료 allowlist가 비어 있습니다.")
        if len(source_ids) != len(set(source_ids)) or any(
            re.fullmatch(r"SRC-[A-Z0-9-]+", source_id) is None
            for source_id in source_ids
        ):
            raise ValueError(f"{row['judgment_id']} 공식자료 source ID가 잘못되었습니다.")
        mapping[row["judgment_id"]] = source_ids
    return mapping


def load_local_official_chunks(root: Path | None = None) -> list[RagChunk]:
    repo_root = root or _repo_root()
    manifest = repo_root / "data" / "rag" / "metadata" / "official_sources.jsonl"
    chunks: list[RagChunk] = []
    for line in manifest.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        if record["distribution_mode"] != "local_source":
            continue
        local_path = repo_root / record["local_path"]
        metadata = RagSourceMetadata(
            source_id=record["source_id"],
            document_title=record["title"],
            institution=record["institution"],
            document_type=record["document_type"],
            article_or_section=record["article_or_section"],
            effective_date=record["effective_or_published_date"],
            source_url=record["source_url"],
            collected_date=date.fromisoformat(record["retrieved_at"]),
            source_sha256=record["content_sha256"],
            usage_terms=record["usage_terms"],
        )
        text = local_path.read_text(encoding="utf-8")
        chunks.extend(
            chunk_sections(metadata, [(record["article_or_section"], text)])
        )
    if not chunks:
        raise ValueError("검색 가능한 공식 로컬 원문이 없습니다.")
    return chunks


def build_evidence_service(
    chunks: Sequence[RagChunk],
    *,
    embedding_provider: EmbeddingProvider | None = None,
    rerank_provider: RerankProvider | None = None,
    persist_path: Path | str | None = None,
    chroma_client: Any | None = None,
    collection_name: str = DEFAULT_COLLECTION_NAME,
    chunking_version: str = DEFAULT_CHUNKING_VERSION,
    rebuild_stale: bool = True,
) -> EvidenceRetrievalService:
    """Hybrid runtime을 만들고 외부 provider·인덱스 실패 시 BM25로 축소한다."""
    bm25 = BM25Index(chunks)
    retriever: Retriever = bm25
    if embedding_provider is not None:
        try:
            vector = ChromaVectorIndex(
                embedding_provider,
                persist_path=persist_path,
                client=chroma_client,
                collection_name=collection_name,
                chunking_version=chunking_version,
            )
            try:
                vector.index_chunks(chunks)
            except StaleIndexError:
                if not rebuild_stale:
                    raise
                vector.index_chunks(chunks, rebuild=True)
            retriever = HybridRetriever(bm25, vector)
        except Exception:
            # RAG 부품 장애가 규칙 분석을 실패시키지 않도록 lexical 경로를 보존한다.
            retriever = bm25
    reranker = (
        RerankingService(rerank_provider) if rerank_provider is not None else None
    )
    return EvidenceRetrievalService(retriever, reranker)


def _embedding_key_available() -> bool:
    return bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))


@lru_cache(maxsize=1)
def get_default_evidence_service() -> EvidenceRetrievalService:
    """로컬 MVP 기본 경로: Chroma hybrid → Cohere rerank, 키 없으면 BM25."""
    chunks = load_local_official_chunks()
    embedding_provider = GeminiEmbeddingProvider() if _embedding_key_available() else None
    rerank_provider = CohereRerankProvider() if os.getenv("COHERE_API_KEY") else None
    return build_evidence_service(
        chunks,
        embedding_provider=embedding_provider,
        rerank_provider=rerank_provider,
        persist_path=_repo_root() / "data" / "rag" / "index" / "chroma",
    )
