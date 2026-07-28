from __future__ import annotations

import json
from pathlib import Path

import pytest

from lease_companion_ai.evaluation.ragas_online import (
    RagasLlmCase,
    evaluate_ragas_llm_cases,
    load_ragas_llm_cases,
)


class FakeMetric:
    def __init__(self, name: str, scores: list[float]) -> None:
        self.name = name
        self._scores = iter(scores)
        self.samples = []

    def single_turn_score(self, sample):
        self.samples.append(sample)
        return next(self._scores)


def test_load_ragas_llm_cases_requires_locked_test_split(tmp_path: Path) -> None:
    path = tmp_path / "cases.jsonl"
    path.write_text(
        json.dumps(
            {
                "case_id": "RAGAS-001",
                "split": "test",
                "user_input": "무엇을 확인해야 하나요?",
                "response": "등기 소유자를 확인하세요.",
                "retrieved_contexts": ["등기 소유자와 계약 상대를 확인한다."],
                "reference": "등기 소유자 확인",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    cases = load_ragas_llm_cases(path)

    assert cases[0].case_id == "RAGAS-001"
    assert cases[0].split == "test"


def test_load_ragas_llm_cases_rejects_empty_context(tmp_path: Path) -> None:
    path = tmp_path / "cases.jsonl"
    path.write_text(
        json.dumps(
            {
                "case_id": "RAGAS-001",
                "split": "test",
                "user_input": "질문",
                "response": "응답",
                "retrieved_contexts": [],
                "reference": "정답",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="retrieved_contexts"):
        load_ragas_llm_cases(path)


def test_evaluate_ragas_llm_cases_records_case_scores_and_macro() -> None:
    cases = [
        RagasLlmCase(
            case_id="RAGAS-001",
            split="test",
            user_input="질문 1",
            response="응답 1",
            retrieved_contexts=("근거 1",),
            reference="정답 1",
        ),
        RagasLlmCase(
            case_id="RAGAS-002",
            split="test",
            user_input="질문 2",
            response="응답 2",
            retrieved_contexts=("근거 2",),
            reference="정답 2",
        ),
    ]
    faithfulness = FakeMetric("faithfulness", [1.0, 0.5])
    relevancy = FakeMetric("answer_relevancy", [0.8, 0.6])

    report = evaluate_ragas_llm_cases(
        cases,
        metrics=[faithfulness, relevancy],
        judge_model="gemini/test",
        embedding_model="gemini-embedding-001",
        measured_at="2026-07-28",
        ragas_version="0.3.9",
    )

    assert report["external_provider_calls_required"] is True
    assert report["evaluated_case_count"] == 2
    assert report["metrics"]["faithfulness"]["macro_average"] == 0.75
    assert report["metrics"]["answer_relevancy"]["macro_average"] == 0.7
    assert report["case_scores"][0]["faithfulness"] == 1.0
    sample = faithfulness.samples[0]
    assert sample.user_input == "질문 1"
    assert sample.retrieved_contexts == ["근거 1"]
