"""실제 계약 점검·계약 연습 한 사이클의 provider 메타데이터를 수집한다."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
AI_SRC = ROOT / "ai" / "src"
if str(AI_SRC) not in sys.path:
    sys.path.insert(0, str(AI_SRC))

from lease_companion_ai.classification.service import ClassificationService  # noqa: E402
from lease_companion_ai.evaluation.cycle_metrics import build_cycle_summary  # noqa: E402
from lease_companion_ai.evaluation.provider_metrics import load_jsonl_metrics  # noqa: E402
from lease_companion_ai.generation.service import GenerationService  # noqa: E402
from lease_companion_ai.pipelines.classified_analysis import (  # noqa: E402
    analyze_with_classification,
)
from lease_companion_ai.pipelines.minimum_mvp import extract_documents  # noqa: E402
from lease_companion_ai.providers.cohere_rerank import CohereRerankProvider  # noqa: E402
from lease_companion_ai.providers.gemini_classification import (  # noqa: E402
    GeminiClassificationProvider,
)
from lease_companion_ai.providers.gemini_embeddings import (  # noqa: E402
    GeminiEmbeddingProvider,
)
from lease_companion_ai.providers.gemini_generation import (  # noqa: E402
    GeminiGenerationProvider,
)
from lease_companion_ai.providers.gemini_practice import (  # noqa: E402
    GeminiPracticeProvider,
)
from lease_companion_ai.providers.gemini_practice_dialogue import (  # noqa: E402
    GeminiPracticeDialogueProvider,
)
from lease_companion_ai.rag.clause_service import (  # noqa: E402
    build_special_clause_retrieval_service,
)
from lease_companion_ai.rag.service import (  # noqa: E402
    get_default_evidence_service,
)
from lease_companion_ai.schemas.adapters import (  # noqa: E402
    build_snapshot,
    confirm_document,
    document_from_legacy,
)
from lease_companion_ai.schemas.simulation import (  # noqa: E402
    PracticeTurnInput,
)
from lease_companion_ai.schemas.unified import ContractContext  # noqa: E402
from lease_companion_ai.simulation.models import load_practice_assets  # noqa: E402
from lease_companion_ai.simulation.service import PracticeSimulationService  # noqa: E402


def _require_keys(*names: str) -> None:
    missing = [name for name in names if not os.getenv(name)]
    if missing:
        raise SystemExit("필수 API 키가 없습니다: " + ", ".join(missing))


def _actual_snapshot(
    extraction: dict[str, Any],
    *,
    contract_id: int,
) -> tuple[Any, ContractContext]:
    contract = extraction["contract"]
    registry = extraction["registry"]
    if not contract.get("read_ok") or not registry.get("read_ok"):
        raise RuntimeError("계약서 또는 등기사항증명서 구조화에 실패했습니다.")
    contract_doc = confirm_document(
        document_from_legacy(contract, document_id="cycle-contract-document")
    )
    registry_doc = confirm_document(
        document_from_legacy(registry, document_id="cycle-registry-document")
    )
    context = ContractContext(
        contract_id=contract_id,
        contract_type="보증부 월세",
        contract_stage="계약금 입금 전",
        deposit_paid=False,
        signed=False,
        is_proxy_contract=False,
    )
    snapshot = build_snapshot(
        input_snapshot_id="cycle-actual-snapshot-001",
        contract_id=contract_id,
        contract_context=context,
        contract_doc=contract_doc,
        registry_doc=registry_doc,
        confirmed_at=datetime.now(timezone.utc),
    )
    return snapshot, context


def run_actual_contract_cycle(
    contract_path: Path,
    registry_path: Path,
) -> dict[str, Any]:
    _require_keys("GEMINI_API_KEY", "COHERE_API_KEY")
    extraction = extract_documents(
        contract_path.read_bytes(),
        contract_path.name,
        registry_path.read_bytes(),
        registry_path.name,
    )
    snapshot, context = _actual_snapshot(extraction, contract_id=900001)
    classification, analysis = analyze_with_classification(
        snapshot,
        analysis_run_id="cycle-actual-analysis-001",
        classification_service=ClassificationService(
            GeminiClassificationProvider()
        ),
    )
    analysis = get_default_evidence_service().enrich(analysis)
    clause_service = build_special_clause_retrieval_service(
        embedding_provider=GeminiEmbeddingProvider(),
        rerank_provider=CohereRerankProvider(),
        persist_path=ROOT / "data/rag/index/chroma-cycle-special",
    )
    analysis = clause_service.enrich(analysis)
    generation = GenerationService(GeminiGenerationProvider()).generate(
        analysis, context
    )
    return {
        "classification_method": classification.classification_method.value,
        "rule_count": len(analysis.results),
        "judgment_count": len(analysis.judgments),
        "special_clause_count": len(analysis.special_clause_reviews),
        "generation_item_count": (
            len(generation.items)
            + len(generation.judgment_items)
            + len(generation.special_clause_items)
        ),
    }


def run_simulation_cycle(scenario_dir: Path) -> dict[str, Any]:
    _require_keys("GEMINI_API_KEY")
    scenario, answer_key = load_practice_assets(
        scenario_dir / "scenario.json",
        scenario_dir / "answer-key.json",
    )
    service = PracticeSimulationService(
        scenario,
        answer_key,
        GeminiPracticeProvider(),
        dialogue_provider=GeminiPracticeDialogueProvider(),
    )
    now = datetime.now(timezone.utc)
    session = service.start_session("cycle-simulation-001", 900001, now)
    answers = {
        "TURN-01": "보증금은 언제 돌려주시나요?",
        "TURN-02": "그 약속을 계약서에 적어 주세요.",
        "TURN-03": "오늘은 계약하지 않겠습니다.",
    }
    evaluations: list[str] = []
    for turn_id in ("TURN-01", "TURN-02", "TURN-03"):
        step = service.submit(
            session,
            PracticeTurnInput(
                session_id=session.session_id,
                turn_id=turn_id,
                user_answer=answers[turn_id],
                timed_out=False,
                response_time_seconds=3.0,
            ),
            occurred_at=datetime.now(timezone.utc),
        )
        session = step.session
        if step.evaluation is None:
            raise RuntimeError("시뮬레이션 턴 평가가 없습니다.")
        evaluations.append(step.evaluation.answer_category)
    final_step = service.submit(
        session,
        PracticeTurnInput(
            session_id=session.session_id,
            turn_id="ACTION-SELECTION",
            selected_action="보류",
            response_time_seconds=2.0,
        ),
        occurred_at=datetime.now(timezone.utc),
    )
    if final_step.result is None:
        raise RuntimeError("시뮬레이션 결과가 생성되지 않았습니다.")
    return {
        "scenario_id": scenario.scenario_id,
        "turn_count": 3,
        "evaluation_categories": evaluations,
        "completed": final_step.session.status == "completed",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        required=True,
        choices=("actual_contract", "simulation"),
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--pricing", type=Path, required=True)
    parser.add_argument("--contract", type=Path)
    parser.add_argument("--registry", type=Path)
    parser.add_argument(
        "--scenario-dir",
        type=Path,
        default=(
            ROOT
            / "data/sample/practice-scenarios/PRACTICE-DEFERRED-REFUND-001"
        ),
    )
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("기존 로그 덮어쓰기를 거부합니다: " + str(args.output))
    os.environ["PROVIDER_METRICS_JSONL"] = str(args.output)
    os.environ["PROVIDER_PRICING_JSON"] = str(args.pricing)

    started = datetime.now(timezone.utc)
    if args.mode == "actual_contract":
        if args.contract is None or args.registry is None:
            parser.error("actual_contract에는 --contract와 --registry가 필요합니다.")
        outcome = run_actual_contract_cycle(args.contract, args.registry)
    else:
        outcome = run_simulation_cycle(args.scenario_dir)
    finished = datetime.now(timezone.utc)

    calls = load_jsonl_metrics(args.output)
    summary = build_cycle_summary(
        mode=args.mode,
        calls=calls,
        cycle_count=1,
    )
    summary.update(
        {
            "started_at": started.isoformat(),
            "finished_at": finished.isoformat(),
            "wall_clock_ms": int((finished - started).total_seconds() * 1_000),
            "outcome": outcome,
        }
    )
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"cycle={args.mode} calls={summary['call_count']} "
        f"failures={summary['failure_count']} "
        f"known_cost_usd={summary['known_cost_usd']}"
    )


if __name__ == "__main__":
    main()
