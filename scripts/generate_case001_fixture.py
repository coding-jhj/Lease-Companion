"""CASE-001 대표 fixture 생성기 — AI·Backend·Frontend 공통 데이터 계약 예시.

시나리오(수정 전 → 수정 → 스냅샷 → 분석):
- 추출 단계에서 contract.account_holder를 읽지 못해 null(실패)로 나온다.
- registry.issue_date는 값은 읽었지만 '불확실' 신뢰도다 (confidence 3등급 표시 예시).
- 사용자가 account_holder를 "이정훈"으로 수정하면 effective value가 goldset과 같아져
  R01~R10 결과가 data/sample/expected-results/rule_goldset.jsonl 의 CASE-001과 일치한다.

식별자: case_id=CASE-001(합성 평가 사례) / contract_id=1001(별도 데모 계약 건).

실행:
    conda run -n lease-py310 python scripts/generate_case001_fixture.py

출력은 결정적(고정 타임스탬프·정렬) — 재실행 시 git diff가 없어야 한다.
스크립트는 쓰기 전에 rule goldset과 실제 규칙 실행 결과가 일치하는지 자체 검증한다.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ai" / "src"))

from lease_companion_ai.schemas.adapters import (  # noqa: E402
    analyze_snapshot,
    apply_correction_request,
    build_snapshot,
    confirm_document,
)
from lease_companion_ai.schemas.unified import (  # noqa: E402
    Confidence,
    ContractContext,
    ContractStage,
    ContractType,
    CorrectionRequest,
    DocumentExtraction,
    DocumentType,
    ExtractedField,
    FieldCorrection,
    SourceEvidence,
)

OUTPUT_DIR = ROOT / "data" / "sample" / "fixtures" / "case-001"

CASE_ID = "CASE-001"
CONTRACT_ID = 1001
CONTRACT_DOC_ID = "DOC-1001-CONTRACT"
REGISTRY_DOC_ID = "DOC-1001-REGISTRY"
SNAPSHOT_ID = "SNAP-1001-001"
ANALYSIS_RUN_ID = "RUN-1001-001"
CONFIRMED_AT = datetime(2026, 7, 16, 12, 0, 0, tzinfo=timezone(timedelta(hours=9)))

KST_ADDRESS = "서울특별시 가온구 나래로 12, 305동 1201호"


def _extracted(name: str, value, page: int | None = None, text: str | None = None) -> ExtractedField:
    return ExtractedField(
        field_name=name,
        extracted_value=value,
        confidence=Confidence.EXTRACTED,
        source_evidence=SourceEvidence(page=page, text=text),
    )


def contract_extraction() -> DocumentExtraction:
    """수정 전 계약서 추출 결과 — goldset 값 + account_holder 판독 실패."""
    fields = {
        "landlord_name": _extracted("landlord_name", "이정훈", 1, "임대인 성명: 이정훈"),
        "tenant_name": _extracted("tenant_name", "강해린", 1, "임차인 성명: 강해린"),
        "property_address": _extracted("property_address", KST_ADDRESS, 1, f"소재지: {KST_ADDRESS}"),
        "deposit": _extracted("deposit", 300000000, 1, "보증금 금 삼억원정 (₩300,000,000)"),
        # 판독 실패 예시: 값 null + failure_reason, page/text도 null (null 원문 증거 처리 예시).
        "account_holder": ExtractedField(
            field_name="account_holder",
            confidence=Confidence.FAILED,
            failure_reason="입금 계좌 예금주 칸을 문서에서 읽지 못했습니다.",
        ),
        "deposit_return_condition": _extracted(
            "deposit_return_condition", "명확", 2, "임대인은 계약 종료일에 보증금 전액을 반환한다."
        ),
        "repair_responsibility": _extracted(
            "repair_responsibility", "명확", 2, "주요 설비 하자 수선은 임대인이 부담한다."
        ),
        "rights_change_clause_present": _extracted("rights_change_clause_present", True, 2, "특약 제3항"),
    }
    return DocumentExtraction(
        document_id=CONTRACT_DOC_ID, document_type=DocumentType.CONTRACT, fields=fields
    )


def registry_extraction() -> DocumentExtraction:
    """수정 전 등기사항증명서 추출 결과 — goldset 값 + issue_date 불확실."""
    fields = {
        "owner_names": _extracted("owner_names", ["박성우"], 1, "소유자 박성우"),
        "property_address": _extracted("property_address", KST_ADDRESS, 1, f"(도로명주소) {KST_ADDRESS}"),
        # 불확실 예시: 값은 있으나 신뢰도 낮음 — 화면에서 3등급 구분 표시용.
        "issue_date": ExtractedField(
            field_name="issue_date",
            extracted_value="2026-07-28",
            confidence=Confidence.UNCERTAIN,
            source_evidence=SourceEvidence(page=3, text="열람일시: 2026년 07월 28일"),
        ),
        "mortgage_present": _extracted("mortgage_present", True, 2, "을구 근저당권설정 채권최고액 금240,000,000원"),
        "seizure_present": _extracted("seizure_present", False),
        "provisional_seizure_present": _extracted("provisional_seizure_present", False),
        "trust_present": _extracted("trust_present", False),
    }
    return DocumentExtraction(
        document_id=REGISTRY_DOC_ID, document_type=DocumentType.REGISTRY, fields=fields
    )


def correction_request() -> CorrectionRequest:
    return CorrectionRequest(
        contract_id=CONTRACT_ID,
        corrections=[
            FieldCorrection(
                document_type=DocumentType.CONTRACT,
                field_name="account_holder",
                corrected_value="이정훈",
            )
        ],
    )


def contract_context() -> ContractContext:
    return ContractContext(
        contract_id=CONTRACT_ID,
        contract_type=ContractType.JEONSE,
        contract_stage=ContractStage.BEFORE_DEPOSIT,
        deposit_paid=False,
        signed=False,
        move_in_date=None,
        balance_payment_date=None,
        is_proxy_contract=False,
    )


def _self_check(analysis) -> None:
    goldset_path = ROOT / "data" / "sample" / "expected-results" / "rule_goldset.jsonl"
    gold = None
    for line in goldset_path.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        if record["case_id"] == CASE_ID:
            gold = {item["rule_id"]: item["status"] for item in record["gold_rules"]}
            break
    assert gold is not None, "rule_goldset.jsonl에 CASE-001이 없습니다."
    actual = {result.rule_id: result.status.value for result in analysis.results}
    assert actual == gold, f"규칙 결과가 goldset과 다릅니다: {actual} != {gold}"


def _write(path: Path, model) -> None:
    payload = json.dumps(model.model_dump(mode="json"), ensure_ascii=False, indent=2, sort_keys=True)
    path.write_text(payload + "\n", encoding="utf-8")
    print(f"wrote {path.relative_to(ROOT)}")


def main() -> None:
    contract_doc = contract_extraction()
    registry_doc = registry_extraction()
    request = correction_request()

    corrected = apply_correction_request(
        {DocumentType.CONTRACT: contract_doc, DocumentType.REGISTRY: registry_doc}, request
    )
    confirmed_contract = confirm_document(corrected[DocumentType.CONTRACT])
    confirmed_registry = confirm_document(corrected[DocumentType.REGISTRY])
    snapshot = build_snapshot(
        input_snapshot_id=SNAPSHOT_ID,
        contract_id=CONTRACT_ID,
        case_id=CASE_ID,
        contract_doc=confirmed_contract,
        registry_doc=confirmed_registry,
        confirmed_at=CONFIRMED_AT,
    )
    analysis = analyze_snapshot(snapshot, analysis_run_id=ANALYSIS_RUN_ID)
    _self_check(analysis)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _write(OUTPUT_DIR / "contract_context.json", contract_context())
    _write(OUTPUT_DIR / "contract_extraction.json", contract_doc)
    _write(OUTPUT_DIR / "registry_extraction.json", registry_doc)
    _write(OUTPUT_DIR / "correction_request.json", request)
    _write(OUTPUT_DIR / "input_snapshot.json", snapshot)
    _write(OUTPUT_DIR / "analysis_run_result.json", analysis)


if __name__ == "__main__":
    main()
