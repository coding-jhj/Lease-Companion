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
from lease_companion_ai.rag.indexing.chunker import chunk_sections, normalize_source_text
from lease_companion_ai.rag.models import (
    ClauseRetrievalQuery,
    EvidenceQuery,
    JudgmentRetrievalQuery,
    RagChunk,
    RagSourceMetadata,
    RetrievalHit,
    RetrievalQuery,
)
from lease_companion_ai.rag.reranking.service import RerankingService
from lease_companion_ai.rag.retrieval.bm25 import BM25Index, Tokenizer
from lease_companion_ai.rag.retrieval.hybrid import HybridRetriever
from lease_companion_ai.routing.models import (
    ProcessingStage,
    RouteTarget,
    RoutingDecision,
    RoutingFailureReason,
)
from lease_companion_ai.routing.service import RoutingService
from lease_companion_ai.schemas.unified import (
    JUDGMENT_IDS,
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
    routing_decisions: tuple[RoutingDecision, ...] = ()


class EvidenceRetrievalService:
    def __init__(
        self,
        retriever: Retriever,
        reranker: RerankingService | None = None,
        *,
        judgment_source_ids: Mapping[str, tuple[str, ...]] | None = None,
        judgment_search_contexts: Mapping[str, str] | None = None,
        rule_source_ids: Mapping[str, tuple[str, ...]] | None = None,
        rule_search_contexts: Mapping[str, str] | None = None,
        source_texts: Mapping[str, str] | None = None,
        initial_routing_decisions: Sequence[RoutingDecision] = (),
    ) -> None:
        self._retriever = retriever
        self._reranker = reranker
        self._source_texts = dict(
            source_texts if source_texts is not None else load_source_full_texts()
        )
        self._judgment_source_ids = dict(
            judgment_source_ids
            if judgment_source_ids is not None
            else load_judgment_source_ids()
        )
        self._judgment_search_contexts = dict(
            judgment_search_contexts
            if judgment_search_contexts is not None
            else load_judgment_search_contexts()
        )
        self._rule_search_contexts = dict(
            rule_search_contexts
            if rule_search_contexts is not None
            else load_rule_search_contexts()
        )
        self._rule_source_ids = dict(
            rule_source_ids
            if rule_source_ids is not None
            else load_rule_source_ids()
        )
        self._initial_routing_decisions = tuple(initial_routing_decisions)

    def search(
        self,
        query: EvidenceQuery,
        *,
        top_k: int = 20,
        top_n: int = 5,
    ) -> EvidenceSearchResult:
        if (
            isinstance(query, JudgmentRetrievalQuery)
            and query.evidence_search_context is None
        ):
            context = self._judgment_search_contexts.get(query.judgment_id)
            if context:
                query = query.model_copy(
                    update={"evidence_search_context": context}
                )
        routing_decisions = list(self._initial_routing_decisions)
        try:
            if isinstance(self._retriever, HybridRetriever):
                routed_search = self._retriever.search_routed(query, top_k=top_k)
                hits = routed_search.value
                routing_decisions.append(routed_search.decision)
            else:
                hits = self._retriever.search(query, top_k=top_k)
        except ProviderError:
            return EvidenceSearchResult(
                (),
                provider_fallback_used=True,
                routing_decisions=tuple(routing_decisions),
            )
        if query.allowed_source_ids:
            allowed = set(query.allowed_source_ids)
            hits = [
                hit for hit in hits if hit.chunk.metadata.source_id in allowed
            ]
            hits = [
                hit.model_copy(update={"rank": rank})
                for rank, hit in enumerate(hits, start=1)
            ]
        if isinstance(query, ClauseRetrievalQuery):
            allowed_sections = set(query.allowed_section_pairs)
            hits = [
                hit
                for hit in hits
                if (hit.chunk.metadata.source_id, hit.chunk.section)
                in allowed_sections
            ]
            hits = [
                hit.model_copy(update={"rank": rank})
                for rank, hit in enumerate(hits, start=1)
            ]
        fallback = any(decision.fallback_used for decision in routing_decisions) or (
            bool(hits) and all(hit.retrieval_method == "bm25" for hit in hits)
        )
        if self._reranker is None:
            return EvidenceSearchResult(
                tuple(hits[:top_n]),
                provider_fallback_used=fallback,
                routing_decisions=tuple(routing_decisions),
            )
        routed_rerank = self._reranker.rerank_routed(query, hits, top_n=top_n)
        reranked = routed_rerank.value
        routing_decisions.append(routed_rerank.decision)
        fallback = fallback or routed_rerank.decision.fallback_used
        if reranked and any(hit.retrieval_method != "rerank" for hit in reranked):
            fallback = True
        return EvidenceSearchResult(
            tuple(reranked),
            provider_fallback_used=fallback,
            routing_decisions=tuple(routing_decisions),
        )

    def enrich(self, analysis: AnalysisRunResult) -> AnalysisRunResult:
        enriched: list[RuleResult] = []
        for result in analysis.results:
            evidence: list[OfficialSource] = []
            if result.triggers_actions:
                query = RetrievalQuery(
                    rule_id=result.rule_id,
                    rule_name=result.rule_name,
                    status=result.status,
                    allowed_source_ids=self._rule_source_ids.get(result.rule_id, ()),
                    evidence_search_context=self._rule_search_contexts.get(
                        result.rule_id
                    ),
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
                            summary=hit.chunk.text,
                            source_text=self._source_texts.get(metadata.source_id),
                            source_url=metadata.source_url,
                            retrieval_method=hit.retrieval_method,
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
                            summary=hit.chunk.text,
                            source_text=self._source_texts.get(metadata.source_id),
                            source_url=metadata.source_url,
                            retrieval_method=hit.retrieval_method,
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


def load_rule_search_contexts(path: Path | None = None) -> dict[str, str]:
    """규칙별 공식 근거 설명을 개인정보 없는 검색 확장 문맥으로 읽는다."""
    source_path = path or _repo_root() / "data" / "rules" / "rule_evidence_map.csv"
    with source_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    contexts: dict[str, list[str]] = {}
    for row in rows:
        rule_id = row["rule_id"].strip()
        relevance_note = row["relevance_note"].strip()
        if re.fullmatch(r"R(?:0[1-9]|1[0-9]|2[0-4])", rule_id) is None or not relevance_note:
            raise ValueError("R 공식 근거 검색 문맥이 잘못되었습니다.")
        notes = contexts.setdefault(rule_id, [])
        if relevance_note not in notes:
            notes.append(relevance_note)
    expected_ids = [f"R{index:02d}" for index in range(1, 25)]
    if list(contexts) != expected_ids:
        raise ValueError("rule_evidence_map에는 R01~R24가 순서대로 있어야 합니다.")
    return {rule_id: " ".join(notes) for rule_id, notes in contexts.items()}


def load_rule_source_ids(path: Path | None = None) -> dict[str, tuple[str, ...]]:
    """R01~R24의 공식자료 allowlist를 순서까지 보존해 읽는다."""
    source_path = path or _repo_root() / "data" / "rules" / "rule_evidence_map.csv"
    with source_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    mapping: dict[str, list[str]] = {}
    for row in rows:
        rule_id = row["rule_id"].strip()
        source_id = row["source_id"].strip()
        if re.fullmatch(r"R(?:0[1-9]|1[0-9]|2[0-4])", rule_id) is None or re.fullmatch(
            r"SRC-[A-Z0-9-]+", source_id
        ) is None:
            raise ValueError("R 공식자료 allowlist가 잘못되었습니다.")
        source_ids = mapping.setdefault(rule_id, [])
        if source_id in source_ids:
            raise ValueError("R 공식자료 allowlist에는 중복 source ID를 둘 수 없습니다.")
        source_ids.append(source_id)
    expected_ids = [f"R{index:02d}" for index in range(1, 25)]
    if list(mapping) != expected_ids:
        raise ValueError("rule_evidence_map에는 R01~R24가 순서대로 있어야 합니다.")
    return {rule_id: tuple(source_ids) for rule_id, source_ids in mapping.items()}


def load_judgment_source_ids(root: Path | None = None) -> dict[str, tuple[str, ...]]:
    """J 명세의 판정별 공식자료 allowlist를 순서까지 보존해 읽는다."""
    repo_root = root or _repo_root()
    path = repo_root / "data" / "rules" / "judgment_spec.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    expected_ids = list(JUDGMENT_IDS)
    judgment_ids = [row["judgment_id"] for row in rows]
    if judgment_ids != expected_ids:
        raise ValueError("judgment_spec에는 canonical J 순서가 있어야 합니다.")
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


def load_judgment_search_contexts(root: Path | None = None) -> dict[str, str]:
    """용어 불일치가 확인된 J 판정의 정적 검색 확장 문맥을 읽는다."""
    repo_root = root or _repo_root()
    path = repo_root / "data" / "rules" / "judgment_search_context.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    contexts: dict[str, str] = {}
    for row in rows:
        judgment_id = row["judgment_id"].strip()
        search_context = row["search_context"].strip()
        if (
            re.fullmatch(r"J(?:0[1-9]|1[0-2])", judgment_id) is None
            or not search_context
            or judgment_id in contexts
        ):
            raise ValueError("J 공식 근거 검색 문맥이 잘못되었습니다.")
        contexts[judgment_id] = search_context
    if not contexts:
        raise ValueError("J 공식 근거 검색 문맥이 비어 있습니다.")
    return contexts


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


def load_source_full_texts(root: Path | None = None) -> dict[str, str]:
    """source_id → 공식자료 전체 원문. 화면 "전체 보기"에 청크 대신 원문을 쓰기 위함.

    로컬 원문(local_source)만 담고, manifest가 없으면 빈 map을 반환한다(검색 청크로 폴백).
    """
    repo_root = root or _repo_root()
    manifest = repo_root / "data" / "rag" / "metadata" / "official_sources.jsonl"
    if not manifest.exists():
        return {}
    texts: dict[str, str] = {}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        if record["distribution_mode"] != "local_source":
            continue
        local_path = repo_root / record["local_path"]
        texts[record["source_id"]] = normalize_source_text(
            local_path.read_text(encoding="utf-8")
        )
    return texts


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
    bm25_tokenizer: Tokenizer | None = None,
) -> EvidenceRetrievalService:
    """Hybrid runtime을 만들고 외부 provider·인덱스 실패 시 BM25로 축소한다."""
    bm25 = (
        BM25Index(chunks, tokenizer=bm25_tokenizer)
        if bm25_tokenizer is not None
        else BM25Index(chunks)
    )
    retriever: Retriever = bm25
    routing_decisions: list[RoutingDecision] = []
    if embedding_provider is not None:
        def build_hybrid() -> Retriever:
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
            return HybridRetriever(bm25, vector)

        routed_build = RoutingService().execute(
            stage=ProcessingStage.EMBEDDING,
            primary_target=RouteTarget.GEMINI_EMBEDDING,
            fallback_target=RouteTarget.BM25,
            primary=build_hybrid,
            fallback=lambda: bm25,
            handled_errors=(Exception,),
        )
        retriever = routed_build.value
        routing_decisions.append(routed_build.decision)
    else:
        routing_decisions.append(
            RoutingService.fallback_decision(
                stage=ProcessingStage.EMBEDDING,
                primary_target=RouteTarget.GEMINI_EMBEDDING,
                fallback_target=RouteTarget.BM25,
                reason=RoutingFailureReason.PROVIDER_UNAVAILABLE,
                primary_available=False,
            )
        )
    reranker = (
        RerankingService(rerank_provider) if rerank_provider is not None else None
    )
    if reranker is None:
        routing_decisions.append(
            RoutingService.fallback_decision(
                stage=ProcessingStage.RERANK,
                primary_target=RouteTarget.COHERE_RERANK,
                fallback_target=RouteTarget.HYBRID_RANK,
                reason=RoutingFailureReason.PROVIDER_UNAVAILABLE,
                primary_available=False,
            )
        )
    return EvidenceRetrievalService(
        retriever,
        reranker,
        initial_routing_decisions=routing_decisions,
    )


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
