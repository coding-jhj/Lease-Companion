"""Gemini judge를 쓰는 RAGAS LLM 기반 평가."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, Sequence

from ragas.dataset_schema import SingleTurnSample


@dataclass(frozen=True, slots=True)
class RagasLlmCase:
    case_id: str
    split: str
    user_input: str
    response: str
    retrieved_contexts: tuple[str, ...]
    reference: str


class SingleTurnMetric(Protocol):
    name: str

    def single_turn_score(self, sample: SingleTurnSample) -> float: ...


def load_ragas_llm_cases(path: Path) -> list[RagasLlmCase]:
    cases: list[RagasLlmCase] = []
    seen: set[str] = set()
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        payload = json.loads(line)
        case_id = str(payload.get("case_id", "")).strip()
        if not case_id or case_id in seen:
            raise ValueError(f"case_id가 없거나 중복입니다: line {line_number}")
        split = str(payload.get("split", "")).strip()
        if split != "test":
            raise ValueError(f"locked test split만 허용합니다: {case_id}")
        contexts = tuple(
            str(value).strip()
            for value in payload.get("retrieved_contexts", [])
            if str(value).strip()
        )
        if not contexts:
            raise ValueError(f"retrieved_contexts가 비어 있습니다: {case_id}")
        fields = {
            name: str(payload.get(name, "")).strip()
            for name in ("user_input", "response", "reference")
        }
        if any(not value for value in fields.values()):
            raise ValueError(f"필수 평가 텍스트가 비어 있습니다: {case_id}")
        seen.add(case_id)
        cases.append(
            RagasLlmCase(
                case_id=case_id,
                split=split,
                user_input=fields["user_input"],
                response=fields["response"],
                retrieved_contexts=contexts,
                reference=fields["reference"],
            )
        )
    if not cases:
        raise ValueError("RAGAS LLM 평가 사례가 없습니다.")
    return cases


def evaluate_ragas_llm_cases(
    cases: Sequence[RagasLlmCase],
    *,
    metrics: Sequence[SingleTurnMetric],
    judge_model: str,
    embedding_model: str,
    measured_at: str,
    ragas_version: str,
) -> dict[str, Any]:
    if not cases or not metrics:
        raise ValueError("평가 사례와 지표가 필요합니다.")
    case_scores: list[dict[str, Any]] = []
    values: dict[str, list[float]] = {metric.name: [] for metric in metrics}
    failures: list[dict[str, str]] = []
    for case in cases:
        sample = SingleTurnSample(
            user_input=case.user_input,
            response=case.response,
            retrieved_contexts=list(case.retrieved_contexts),
            reference=case.reference,
        )
        row: dict[str, Any] = {"case_id": case.case_id}
        for metric in metrics:
            try:
                score = float(metric.single_turn_score(sample))
                if not math.isfinite(score):
                    raise ValueError("점수가 유한수가 아닙니다.")
                row[metric.name] = score
                values[metric.name].append(score)
            except Exception as exc:
                row[metric.name] = None
                failures.append(
                    {
                        "case_id": case.case_id,
                        "metric": metric.name,
                        "error_type": type(exc).__name__,
                    }
                )
        case_scores.append(row)
    summaries = {
        name: {
            "macro_average": (
                round(sum(scores) / len(scores), 6) if scores else None
            ),
            "scored_case_count": len(scores),
        }
        for name, scores in values.items()
    }
    return {
        "config_version": "ragas-llm-gemini-v1",
        "split": "test",
        "measured_at": measured_at,
        "ragas_version": ragas_version,
        "judge_model": judge_model,
        "embedding_model": embedding_model,
        "external_provider_calls_required": True,
        "evaluated_case_count": len(cases),
        "failed_score_count": len(failures),
        "metrics": summaries,
        "case_scores": case_scores,
        "failures": failures,
        "limitations": [
            "Gemini judge 기반 점수이며 사람 법률 검토를 대체하지 않습니다.",
            "오프라인 ID 기반 Context Precision·Recall과 별도 지표입니다.",
            "잠긴 비식별·합성 test split에만 적용합니다.",
        ],
    }
