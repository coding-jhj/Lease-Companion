"""특약 원문을 catalog source·section 경계 안에서만 검색한다."""

from __future__ import annotations

import csv
import json
import re
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Any, Protocol

from lease_companion_ai.guardrails.pii import PiiTokenizer, contains_raw_pii
from lease_companion_ai.providers.embeddings import EmbeddingProvider
from lease_companion_ai.providers.rerank import RerankProvider
from lease_companion_ai.rag.indexing.chunker import chunk_sections, extract_named_section
from lease_companion_ai.rag.models import (
    ClauseRetrievalQuery,
    RagChunk,
    RagSourceMetadata,
    RetrievalHit,
    SourceSectionFilter,
)
from lease_companion_ai.rag.service import (
    EvidenceRetrievalService,
    EvidenceSearchResult,
    build_evidence_service,
    load_source_full_texts,
)
from lease_companion_ai.rag.retrieval.bm25 import tokenize
from lease_companion_ai.schemas.unified import (
    AnalysisRunResult,
    OfficialSource,
    RuleStatus,
    SpecialClauseReview,
)
from lease_companion_ai.special_clauses.catalog import load_special_clause_catalog
from lease_companion_ai.special_clauses.models import SpecialClauseCandidate


class ClauseEvidenceSearcher(Protocol):
    def search(
        self,
        query: ClauseRetrievalQuery,
        *,
        top_k: int = 20,
        top_n: int = 5,
    ) -> EvidenceSearchResult: ...


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _catalog_entries_by_id():
    return {entry.catalog_id: entry for entry in load_special_clause_catalog()}


def _deidentify_clause(text: str) -> str:
    deidentified = PiiTokenizer().tokenize(text)
    if not deidentified or contains_raw_pii(deidentified):
        raise ValueError("특약 원문 비식별화에 실패했습니다.")
    return deidentified


def _clause_tokenize(text: str) -> list[str]:
    """한국어 조사·활용 차이에도 조항 핵심어를 찾는 결정적 n-gram tokenizer."""

    tokens = tokenize(text)
    expanded = list(tokens)
    for token in tokens:
        if re.fullmatch(r"[가-힣]+", token):
            for size in (2, 3, 4):
                expanded.extend(
                    token[index : index + size]
                    for index in range(len(token) - size + 1)
                )
    return expanded


def build_clause_retrieval_query(
    clause: SpecialClauseCandidate | SpecialClauseReview,
    *,
    status: RuleStatus | str,
    related_result_contexts: tuple[str, ...] = (),
) -> ClauseRetrievalQuery:
    """catalog 후보/카드 → 개인정보 없는 source·section 제한 질의."""

    entries_by_id = _catalog_entries_by_id()
    entries = [entries_by_id[catalog_id] for catalog_id in clause.catalog_ids]
    sections: dict[tuple[str, str], SourceSectionFilter] = {}
    for entry in entries:
        for section in entry.allowed_source_sections:
            key = (section["source_id"], section["article_or_section"])
            sections[key] = SourceSectionFilter(
                source_id=key[0], article_or_section=key[1]
            )
    return ClauseRetrievalQuery(
        clause_id=clause.clause_id,
        catalog_ids=clause.catalog_ids,
        catalog_names=tuple(entry.display_name for entry in entries),
        related_result_contexts=tuple(dict.fromkeys(related_result_contexts)),
        status=RuleStatus(status),
        allowed_source_sections=tuple(sections.values()),
        deidentified_clause_context=_deidentify_clause(clause.original_text),
    )


def _manifest_metadata(root: Path) -> dict[str, tuple[RagSourceMetadata, Path]]:
    manifest = root / "data/rag/metadata/official_sources.jsonl"
    metadata: dict[str, tuple[RagSourceMetadata, Path]] = {}
    for line in manifest.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        if record["distribution_mode"] != "local_source":
            continue
        metadata[record["source_id"]] = (
            RagSourceMetadata(
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
            ),
            root / record["local_path"],
        )
    return metadata


def load_special_clause_chunks(root: Path | None = None) -> list[RagChunk]:
    """근거표의 source·section만 공식 원문에서 추출해 특약 검색 코퍼스를 만든다."""

    repo_root = root or _repo_root()
    evidence_map = repo_root / "data/rules/special_clause_evidence_map.csv"
    with evidence_map.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    source_metadata = _manifest_metadata(repo_root)
    chunks: list[RagChunk] = []
    seen_sections: set[tuple[str, str]] = set()
    for row in rows:
        source_id = row["source_id"].strip()
        section = row["article_or_section"].strip()
        key = (source_id, section)
        if key in seen_sections:
            continue
        seen_sections.add(key)
        if source_id not in source_metadata:
            raise ValueError(f"특약 공식 원문이 로컬 corpus에 없습니다: {source_id}")
        metadata, source_path = source_metadata[source_id]
        section_text = extract_named_section(
            source_path.read_text(encoding="utf-8"), section
        )
        chunks.extend(
            chunk_sections(
                metadata.model_copy(update={"article_or_section": section}),
                [(section, f"{section}\n{section_text}")],
            )
        )
    if not chunks:
        raise ValueError("검색 가능한 특약 공식 근거가 없습니다.")
    return chunks


class SpecialClauseRetrievalService:
    """특약 카드의 R/J는 보존하고 공식 근거만 채운다."""

    def __init__(
        self,
        evidence_service: ClauseEvidenceSearcher,
        *,
        source_texts: Mapping[str, str] | None = None,
    ) -> None:
        self.evidence_service = evidence_service
        self._source_texts = dict(
            source_texts if source_texts is not None else load_source_full_texts()
        )

    def search(self, query: ClauseRetrievalQuery) -> EvidenceSearchResult:
        result = self.evidence_service.search(query, top_k=20, top_n=5)
        deduplicated: list[RetrievalHit] = []
        seen: set[tuple[str, str]] = set()
        for hit in result.hits:
            key = (hit.chunk.metadata.source_id, hit.chunk.section)
            if key in seen:
                continue
            seen.add(key)
            deduplicated.append(hit.model_copy(update={"rank": len(deduplicated) + 1}))
            if len(deduplicated) == 3:
                break
        return EvidenceSearchResult(
            tuple(deduplicated),
            provider_fallback_used=result.provider_fallback_used,
            routing_decisions=result.routing_decisions,
        )

    @staticmethod
    def _result_contexts(
        analysis: AnalysisRunResult, review: SpecialClauseReview
    ) -> tuple[str, ...]:
        rules = {result.rule_id: result for result in analysis.results}
        judgments = {result.judgment_id: result for result in analysis.judgments}
        contexts = []
        for rule_id in review.related_rule_ids:
            if rule_result := rules.get(rule_id):
                contexts.append(
                    f"{rule_result.rule_id} {rule_result.rule_name} {rule_result.status.value}"
                )
        for judgment_id in review.related_judgment_ids:
            if judgment_result := judgments.get(judgment_id):
                contexts.append(
                    f"{judgment_result.judgment_id} {judgment_result.judgment_name} "
                    f"{judgment_result.status.value}"
                )
        return tuple(contexts)

    def enrich(self, analysis: AnalysisRunResult) -> AnalysisRunResult:
        reviews: list[SpecialClauseReview] = []
        for review in analysis.special_clause_reviews:
            try:
                query = build_clause_retrieval_query(
                    review,
                    status=review.status,
                    related_result_contexts=self._result_contexts(analysis, review),
                )
            except ValueError:
                reviews.append(review.model_copy(update={"evidence_sources": ()}))
                continue
            search_result = self.search(query)
            evidence = tuple(
                OfficialSource(
                    source_id=hit.chunk.metadata.source_id,
                    article_or_section=hit.chunk.section,
                    title=hit.chunk.metadata.document_title,
                    institution=hit.chunk.metadata.institution,
                    summary=hit.chunk.text,
                    source_text=self._source_texts.get(hit.chunk.metadata.source_id),
                    source_url=hit.chunk.metadata.source_url,
                    retrieval_method=hit.retrieval_method,
                )
                for hit in search_result.hits
            )
            reviews.append(review.model_copy(update={"evidence_sources": evidence}))
        return AnalysisRunResult.model_validate(
            analysis.model_copy(update={"special_clause_reviews": reviews}).model_dump()
        )


def build_special_clause_retrieval_service(
    *,
    chunks: Sequence[RagChunk] | None = None,
    embedding_provider: EmbeddingProvider | None = None,
    rerank_provider: RerankProvider | None = None,
    persist_path: Path | str | None = None,
    chroma_client: Any | None = None,
) -> SpecialClauseRetrievalService:
    corpus = list(chunks) if chunks is not None else load_special_clause_chunks()
    evidence_service: EvidenceRetrievalService = build_evidence_service(
        corpus,
        embedding_provider=embedding_provider,
        rerank_provider=rerank_provider,
        persist_path=persist_path,
        chroma_client=chroma_client,
        bm25_tokenizer=_clause_tokenize,
    )
    return SpecialClauseRetrievalService(evidence_service)
