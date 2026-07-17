"""규칙 결과를 변경하지 않고 실제 검색된 공식 근거만 연결한다."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Protocol

from lease_companion_ai.providers.errors import ProviderError
from lease_companion_ai.rag.indexing.chunker import chunk_sections
from lease_companion_ai.rag.models import RagChunk, RagSourceMetadata, RetrievalHit, RetrievalQuery
from lease_companion_ai.rag.reranking.service import RerankingService
from lease_companion_ai.rag.retrieval.bm25 import BM25Index
from lease_companion_ai.schemas.unified import AnalysisRunResult, OfficialSource, RuleResult


class Retriever(Protocol):
    def search(
        self, query: RetrievalQuery | str, *, top_k: int = 20
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
    ) -> None:
        self._retriever = retriever
        self._reranker = reranker

    def search(
        self,
        query: RetrievalQuery,
        *,
        top_k: int = 20,
        top_n: int = 5,
    ) -> EvidenceSearchResult:
        try:
            hits = self._retriever.search(query, top_k=top_k)
        except ProviderError:
            return EvidenceSearchResult((), provider_fallback_used=True)
        fallback = bool(hits) and all(hit.retrieval_method == "bm25" for hit in hits)
        if self._reranker is None:
            return EvidenceSearchResult(tuple(hits[:top_n]), provider_fallback_used=False)
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
        return AnalysisRunResult.model_validate(
            analysis.model_copy(update={"results": enriched}).model_dump()
        )


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


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


@lru_cache(maxsize=1)
def get_local_evidence_service() -> EvidenceRetrievalService:
    return EvidenceRetrievalService(BM25Index(load_local_official_chunks()))
