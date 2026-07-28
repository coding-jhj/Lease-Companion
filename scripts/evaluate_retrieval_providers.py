"""운영 경로(Gemini embedding + BM25 hybrid → Cohere rerank)로 검색 지표를 잰다.

`evaluate_ragas_offline.py`는 외부 호출 없이 BM25만 쓰는 기준선이다.
이 스크립트는 같은 goldset·같은 채점식을 쓰되 검색만 실제 provider 경로로 바꾼다.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AI_SRC = ROOT / "ai" / "src"
if str(AI_SRC) not in sys.path:
    sys.path.insert(0, str(AI_SRC))

from lease_companion_ai.evaluation.ragas_offline import (  # noqa: E402
    RagasIdCase,
    score_ragas_id_cases,
)
from lease_companion_ai.evaluation.retrieval import load_gold_cases  # noqa: E402
from lease_companion_ai.providers.cohere_rerank import CohereRerankProvider  # noqa: E402
from lease_companion_ai.providers.gemini_embeddings import (  # noqa: E402
    GeminiEmbeddingProvider,
)
from lease_companion_ai.rag.service import (  # noqa: E402
    build_evidence_service,
    load_local_official_chunks,
)


def _special_clause_provider_metrics(top_k: int = 3) -> dict:
    """특약 검색도 운영 경로(embedding+rerank)로 잰다. 채점식은 오프라인과 같다."""
    from lease_companion_ai.evaluation.ragas_offline import _read_jsonl
    from lease_companion_ai.rag.clause_service import (
        build_clause_retrieval_query,
        build_special_clause_retrieval_service,
    )
    from lease_companion_ai.schemas.unified import RuleStatus
    from lease_companion_ai.special_clauses.service import match_special_clauses

    service = build_special_clause_retrieval_service(
        embedding_provider=GeminiEmbeddingProvider(),
        rerank_provider=CohereRerankProvider(),
        persist_path=ROOT / "data/rag/index/chroma-eval-provider-special",
    )
    records = _read_jsonl(ROOT / "data/evaluation/special-clauses/retrieval_test.jsonl")
    source_cases: list[RagasIdCase] = []
    section_cases: list[RagasIdCase] = []
    for record in records:
        case_id = str(record["case_id"])
        if not bool(record["expect_evidence"]):
            source_cases.append(RagasIdCase(case_id, (), ()))
            section_cases.append(RagasIdCase(case_id, (), ()))
            continue
        expected_sources = tuple(str(v) for v in record["expected_source_ids"])
        expected_sections = tuple(str(v) for v in record["expected_sections"])
        candidate = match_special_clauses([str(record["text"])])[0]
        query = build_clause_retrieval_query(
            candidate,
            status=RuleStatus.CHECK_NEEDED,
            related_result_contexts=tuple(
                [*candidate.related_rule_ids, *candidate.related_judgment_ids]
            ),
        )
        hits = service.search(query).hits[:top_k]
        source_cases.append(
            RagasIdCase(
                case_id=case_id,
                retrieved_context_ids=tuple(h.chunk.metadata.source_id for h in hits),
                reference_context_ids=expected_sources,
            )
        )
        section_cases.append(
            RagasIdCase(
                case_id=case_id,
                retrieved_context_ids=tuple(
                    f"{h.chunk.metadata.source_id}::{h.chunk.section}" for h in hits
                ),
                reference_context_ids=tuple(
                    f"{source_id}::{section}"
                    for source_id, section in zip(
                        expected_sources, expected_sections, strict=True
                    )
                ),
            )
        )
    sources = score_ragas_id_cases(
        source_cases, scope="special_clause_source_top3_provider", top_k=top_k
    )
    sections = score_ragas_id_cases(
        section_cases, scope="special_clause_source_section_top3_provider", top_k=top_k
    )
    return {
        "source_macro_context_precision": sources.macro_context_precision,
        "source_macro_context_recall": sources.macro_context_recall,
        "section_macro_context_precision": sections.macro_context_precision,
        "section_macro_context_recall": sections.macro_context_recall,
        "evaluated_case_count": sources.evaluated_case_count,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data/evaluation/results/retrieval_provider_metrics.json",
    )
    parser.add_argument("--metrics-jsonl", type=Path)
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()
    for key in ("GEMINI_API_KEY", "COHERE_API_KEY"):
        if not os.getenv(key):
            raise SystemExit(f"{key}가 필요합니다.")
    if args.metrics_jsonl:
        os.environ["PROVIDER_METRICS_JSONL"] = str(args.metrics_jsonl)

    service = build_evidence_service(
        load_local_official_chunks(ROOT),
        embedding_provider=GeminiEmbeddingProvider(),
        rerank_provider=CohereRerankProvider(),
        persist_path=ROOT / "data/rag/index/chroma-eval-provider",
    )
    gold_cases = load_gold_cases(
        ROOT / "data/evaluation/end-to-end/final_testset_rag.jsonl",
        ROOT / "data/evaluation/end-to-end/final_testset_rule.jsonl",
        ROOT / "data/rules/rule_spec.csv",
        ROOT / "data/rules/rule_evidence_map.csv",
    )

    cases: list[RagasIdCase] = []
    fallback_query_count = 0
    for case in gold_cases:
        result = service.search(case.query, top_k=20, top_n=args.top_k)
        if result.provider_fallback_used:
            fallback_query_count += 1
        cases.append(
            RagasIdCase(
                case_id=f"{case.case_id}:{case.query.rule_id}",
                retrieved_context_ids=tuple(
                    hit.chunk.metadata.source_id for hit in result.hits[: args.top_k]
                ),
                reference_context_ids=case.expected_source_ids,
            )
        )
    summary = score_ragas_id_cases(
        cases, scope="general_rag_source_top5_provider", top_k=args.top_k
    )
    special = _special_clause_provider_metrics()

    payload = {
        "measured_at": date.today().isoformat(),
        "split": "test",
        "retrieval_path": "gemini_embedding_bm25_hybrid_then_cohere_rerank",
        "embedding_model": "gemini-embedding-001",
        "rerank_model": "rerank-v4.0-pro",
        "query_count": len(cases),
        "provider_fallback_query_count": fallback_query_count,
        "macro_context_precision": summary.macro_context_precision,
        "macro_context_recall": summary.macro_context_recall,
        "special_clauses": special,
        "case_scores": [
            {
                "case_id": item.case_id,
                "context_precision": item.context_precision,
                "context_recall": item.context_recall,
                "retrieved_context_ids": list(item.retrieved_context_ids),
                "reference_context_ids": list(item.reference_context_ids),
            }
            for item in summary.case_scores
        ],
        "limitations": [
            "허용 출처 화이트리스트가 정답 출처와 같아 precision은 구조적으로 1.0입니다.",
            "의미 있는 값은 recall이며 코퍼스는 6출처·37청크입니다.",
            "provider 폴백이 발생한 쿼리는 BM25 결과이며 provider 성능이 아닙니다.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"provider retrieval: queries={len(cases)} "
        f"recall={summary.macro_context_recall:.4f} "
        f"precision={summary.macro_context_precision:.4f} "
        f"fallback_queries={fallback_query_count} output={args.output}"
    )


if __name__ == "__main__":
    main()
