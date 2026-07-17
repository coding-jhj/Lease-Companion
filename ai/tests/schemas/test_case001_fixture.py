"""CASE-001 대표 fixture와 생성 JSON Schema의 계약 테스트.

jsonschema 라이브러리가 env에 없으므로(설치 금지) JSON Schema 검증은
"생성 파일 == 현재 Pydantic 모델의 model_json_schema()" 일치 확인으로 수행한다.
두 산출물의 원본이 같은 Pydantic 모델이므로 이 일치가 곧 스키마 정합성이다.
"""

import json
from pathlib import Path

import pytest

from lease_companion_ai.schemas.unified import (
    SCHEMA_VERSION,
    AnalysisRunResult,
    Confidence,
    ContractContext,
    CorrectionRequest,
    DocumentExtraction,
    GenerationResult,
    InputSnapshot,
    ResultType,
    VerificationStatus,
)

ROOT = Path(__file__).resolve().parents[3]
FIXTURE_DIR = ROOT / "data" / "sample" / "fixtures" / "case-001"
GENERATED_DIR = ROOT / "data" / "schemas" / "generated"

FIXTURE_MODELS = {
    "contract_context.json": ContractContext,
    "contract_extraction.json": DocumentExtraction,
    "registry_extraction.json": DocumentExtraction,
    "correction_request.json": CorrectionRequest,
    "input_snapshot.json": InputSnapshot,
    "analysis_run_result.json": AnalysisRunResult,
    "generation_result.json": GenerationResult,
}


@pytest.mark.parametrize("filename,model", FIXTURE_MODELS.items())
def test_fixture_files_pass_pydantic_validation(filename, model):
    path = FIXTURE_DIR / filename
    assert path.exists(), f"fixture 없음 — scripts/generate_case001_fixture.py 실행 필요: {path}"
    instance = model.model_validate_json(path.read_text(encoding="utf-8"))
    # 직렬화 왕복 동일성
    assert model.model_validate_json(instance.model_dump_json()) == instance


def test_generated_json_schemas_match_current_models():
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    from generate_unified_schemas import MODELS, build_schema

    for name, model in MODELS.items():
        path = GENERATED_DIR / f"{name}.schema.json"
        assert path.exists(), f"생성 스키마 없음 — scripts/generate_unified_schemas.py 실행 필요: {path}"
        on_disk = json.loads(path.read_text(encoding="utf-8"))
        assert on_disk == build_schema(name, model), f"{name}: 재생성 필요 (모델과 불일치)"
        assert on_disk["x-schema-version"] == SCHEMA_VERSION


def test_fixture_identifiers_are_distinct_roles():
    snapshot = InputSnapshot.model_validate_json(
        (FIXTURE_DIR / "input_snapshot.json").read_text(encoding="utf-8")
    )
    analysis = AnalysisRunResult.model_validate_json(
        (FIXTURE_DIR / "analysis_run_result.json").read_text(encoding="utf-8")
    )
    assert snapshot.case_id == "CASE-001"
    assert snapshot.contract_id == 1001
    assert snapshot.case_id != snapshot.contract_id
    ids = {
        str(snapshot.contract_id),
        snapshot.case_id,
        snapshot.input_snapshot_id,
        analysis.analysis_run_id,
    }
    assert len(ids) == 4  # 역할별로 전부 다른 값
    assert analysis.input_snapshot_id == snapshot.input_snapshot_id
    assert analysis.contract_id == snapshot.contract_id


def test_fixture_shows_correction_flow_and_confidence_grades():
    before = DocumentExtraction.model_validate_json(
        (FIXTURE_DIR / "contract_extraction.json").read_text(encoding="utf-8")
    )
    registry = DocumentExtraction.model_validate_json(
        (FIXTURE_DIR / "registry_extraction.json").read_text(encoding="utf-8")
    )
    request = CorrectionRequest.model_validate_json(
        (FIXTURE_DIR / "correction_request.json").read_text(encoding="utf-8")
    )
    snapshot = InputSnapshot.model_validate_json(
        (FIXTURE_DIR / "input_snapshot.json").read_text(encoding="utf-8")
    )

    # 수정 전: account_holder 판독 실패(null + failure_reason + null 원문 증거)
    failed = before.fields["account_holder"]
    assert failed.extracted_value is None
    assert failed.confidence is Confidence.FAILED
    assert failed.failure_reason
    assert failed.source_evidence.page is None and failed.source_evidence.text is None

    # 수정 요청 → 수정 후: corrected + 최초값(null) 보존 + effective는 수정값
    assert request.corrections[0].field_name == "account_holder"
    after = snapshot.confirmed_fields.contract["account_holder"]
    assert after.verification_status is VerificationStatus.CORRECTED
    assert after.extracted_value is None
    assert after.user_corrected_value == "이정훈"
    assert after.effective_value == "이정훈"

    # 수정하지 않은 필드는 confirmed
    assert (
        snapshot.confirmed_fields.contract["landlord_name"].verification_status
        is VerificationStatus.CONFIRMED
    )

    # confidence 3등급이 fixture 안에서 모두 구분 표시 가능
    grades = {f.confidence for f in before.fields.values()} | {
        f.confidence for f in registry.fields.values()
    }
    assert grades == {Confidence.EXTRACTED, Confidence.UNCERTAIN, Confidence.FAILED}


def test_fixture_analysis_matches_rule_goldset():
    analysis = AnalysisRunResult.model_validate_json(
        (FIXTURE_DIR / "analysis_run_result.json").read_text(encoding="utf-8")
    )
    gold = None
    goldset = ROOT / "data" / "sample" / "expected-results" / "rule_goldset.jsonl"
    for line in goldset.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        if record["case_id"] == "CASE-001":
            gold = {item["rule_id"]: item["status"] for item in record["gold_rules"]}
    assert gold is not None
    assert {r.rule_id: r.status.value for r in analysis.results} == gold
    assert all(
        result.result_type
        is (
            ResultType.FACT_FLAG
            if result.rule_id in {"R03", "R04", "R05", "R07", "R10"}
            else ResultType.JUDGMENT
        )
        for result in analysis.results
    )
    assert all(
        result.triggers_actions
        is (result.status.value not in {"일치", "명확", "적용 제외"})
        for result in analysis.results
    )

def test_fixture_generation_result_links_to_analysis_sources():
    analysis = AnalysisRunResult.model_validate_json(
        (FIXTURE_DIR / "analysis_run_result.json").read_text(encoding="utf-8")
    )
    generation = GenerationResult.model_validate_json(
        (FIXTURE_DIR / "generation_result.json").read_text(encoding="utf-8")
    )
    assert generation.analysis_run_id == analysis.analysis_run_id
    rules = {result.rule_id: result for result in analysis.results}
    assert all(item.rule_id in rules for item in generation.items)
    assert all(
        set(item.source_ids)
        <= {source.source_id for source in rules[item.rule_id].evidence_sources}
        for item in generation.items
    )
