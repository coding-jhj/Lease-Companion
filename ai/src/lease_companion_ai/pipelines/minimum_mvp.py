"""최소 MVP의 인식·추출·규칙 실행 파이프라인."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from lease_companion_ai.extraction.gemini_extractor import (
    ExternalCallBudget,
    GeminiExtractError,
    extract_contract_fields,
    extract_registry_fields,
    extract_scanned_fields,
)
from lease_companion_ai.extraction.minimum_mvp import parse_contract, parse_registry
from lease_companion_ai.ingestion.pdf_text import DocumentReadError, extract_document_text
from lease_companion_ai.ingestion.limits import MAX_FILE_SIZE
from lease_companion_ai.schemas.adapters import (
    analyze_snapshot,
    build_snapshot,
    confirm_document,
    document_from_legacy,
    document_to_legacy,
)
from lease_companion_ai.schemas.minimum_mvp import DocumentExtraction as LegacyDocumentExtraction
from lease_companion_ai.routing.models import (
    ProcessingStage,
    RouteTarget,
    RoutingDecision,
)
from lease_companion_ai.routing.service import RoutingService
from lease_companion_ai.schemas.unified import (
    ContractContext,
    DocumentExtraction as UnifiedDocumentExtraction,
)


_KIND_LABELS = {"contract": "계약서", "registry": "등기사항증명서"}

_CONTRACT_PROVIDER_REPAIR_FIELDS = (
    "building_use",
    "deposit",
    "deposit_korean_amount",
    "monthly_rent",
    "monthly_rent_korean_amount",
    "contract_payment",
    "contract_payment_korean_amount",
    "balance_payment",
    "balance_payment_korean_amount",
    "contract_payment_date",
    "balance_payment_date",
    "move_in_date",
    "start_date",
    "end_date",
    "management_fee_present",
    "management_fee",
    "management_fee_items",
    "account_number",
    "bank_name",
    "special_clauses_present",
    "special_clauses",
)


def _repair_contract_provider_fields(
    fields: dict[str, Any], text: str
) -> tuple[dict[str, Any], list[str]]:
    """Gemini가 비워 둔 명시적 계약값만 결정론적 파서 결과로 보완한다.

    Gemini와 로컬 값이 충돌하면 Gemini 값을 덮어쓰지 않는다. 대리권·보증 가입
    가능 여부처럼 별도 확인이 필요한 필드는 이 보완 대상에 포함하지 않는다.
    """
    repaired = dict(fields)
    local = parse_contract(text)
    repaired_names: list[str] = []
    special_replaced = False

    provider_special = repaired.get("special_clauses")
    local_special = local.fields.get("special_clauses")
    if (
        isinstance(provider_special, list)
        and isinstance(local_special, list)
        and len(local_special) > len(provider_special)
    ):
        # Gemini가 특약 여러 개를 한 문장으로 요약하거나 일부만 반환했더라도,
        # 결정론적 파서가 원문에서 더 많은 문단을 복원했다면 원문 목록을 우선한다.
        repaired["special_clauses"] = local_special
        repaired["special_clauses_present"] = True
        special_replaced = True

    for name in _CONTRACT_PROVIDER_REPAIR_FIELDS:
        if name == "special_clauses" and special_replaced:
            continue
        if name in {"management_fee", "management_fee_items"} and repaired.get("management_fee_present") is False:
            continue
        if name == "special_clauses" and repaired.get("special_clauses_present") is False:
            continue
        provider_value = repaired.get(name)
        local_value = local.fields.get(name)
        provider_missing = provider_value is None or provider_value == [] or provider_value == {}
        local_present = local_value is not None and local_value != [] and local_value != {}
        if provider_missing and local_present:
            repaired[name] = local_value
            repaired_names.append(name)

    warnings = list(local.warnings)
    if special_replaced:
        warnings.append(
            "Gemini가 일부만 반환한 특약을 결정론적 계약서 파서가 복원한 "
            "원문 조항 목록으로 교체했습니다."
        )
    if repaired_names:
        warnings.append(
            "Gemini 미확인 필드를 결정론적 계약서 파서로 보완했습니다: "
            + ", ".join(repaired_names)
        )
    return repaired, warnings


def _repair_registry_provider_fields(
    fields: dict[str, Any], text: str
) -> tuple[dict[str, Any], list[str]]:
    """Gemini의 부분 null을 결정론적 등기 파서로 제한적으로 보완한다.

    현재 소유자 목록이 서로 충돌하면 지분은 합성하지 않는다. 지상권은 명시적인
    활성 등기 탐지만 보완하며 금액이나 법적 효력은 계산하지 않는다.
    """
    repaired = dict(fields)
    local = parse_registry(text)
    local_names = local.fields.get("owner_names")
    provider_names = repaired.get("owner_names")
    names_compatible = (
        local_names is not None
        and (
            provider_names is None
            or set(provider_names) == set(local_names)
        )
    )
    repaired_names: list[str] = []
    if names_compatible:
        for name in ("owner_names", "is_joint_ownership", "owner_shares"):
            if repaired.get(name) is None and local.fields.get(name) is not None:
                repaired[name] = local.fields[name]
                repaired_names.append(name)

    local_ground_right = local.fields.get("ground_right_present")
    if local_ground_right is True and repaired.get("ground_right_present") is not True:
        repaired["ground_right_present"] = True
        repaired_names.append("ground_right_present")
    elif repaired.get("ground_right_present") is None and local_ground_right is False:
        repaired["ground_right_present"] = False
        repaired_names.append("ground_right_present")

    warnings = list(local.warnings)
    if repaired_names:
        warnings.append(
            "Gemini 미확인 필드를 결정론적 등기 파서로 보완했습니다: "
            + ", ".join(repaired_names)
        )
    return repaired, warnings


def _detect_doc_kind(text: str) -> str | None:
    """문서 종류 추정. 확신 있는 구조 표지가 있을 때만 판정하고, 애매하면 None."""
    # PDF 텍스트 레이어는 제목이 "등 기 사 항 …"처럼 글자 간 공백으로 나온다 — 공백 제거 후 판정.
    compact = re.sub(r"\s+", "", text)
    if "등기사항" in compact and any(marker in compact for marker in ("표제부", "갑구", "을구")):
        return "registry"
    if "임대차" in compact and "계약" in compact:
        return "contract"
    return None


def _structure_unified(
    text: str,
    doc_type: str,
    *,
    document_id: str,
    routing_decisions: list[RoutingDecision] | None = None,
) -> UnifiedDocumentExtraction:
    """문서 텍스트 → canonical 통합 추출 결과.

    폴백은 shim이 아니라 graceful degradation: 키 없음·API 실패 시에도 합성 .txt 데모가 동작.
    """
    label = "contract" if doc_type == "contract" else "registry_record"
    def provider_extraction() -> LegacyDocumentExtraction:
        fields = (
            extract_contract_fields(text)
            if doc_type == "contract"
            else extract_registry_fields(text)
        )
        warnings: list[str] = []
        if doc_type == "contract":
            fields, warnings = _repair_contract_provider_fields(fields, text)
        elif doc_type == "registry":
            fields, warnings = _repair_registry_provider_fields(fields, text)
        unconfirmed = [key for key, value in fields.items() if value is None]
        return LegacyDocumentExtraction(label, fields, unconfirmed, warnings)

    def local_extraction() -> LegacyDocumentExtraction:
        parser = parse_contract if doc_type == "contract" else parse_registry
        return parser(text)

    routed = RoutingService().execute(
        stage=ProcessingStage.EXTRACTION,
        primary_target=RouteTarget.GEMINI_EXTRACTION,
        fallback_target=RouteTarget.LOCAL_EXTRACTION,
        primary=provider_extraction,
        fallback=local_extraction,
        handled_errors=(GeminiExtractError,),
    )
    if routing_decisions is not None:
        routing_decisions.append(routed.decision)
    return document_from_legacy(routed.value.to_dict(), document_id=document_id)


def _structure(
    text: str,
    doc_type: str,
    *,
    routing_decisions: list[RoutingDecision] | None = None,
) -> dict[str, Any]:
    """기존 minimum MVP 응답 호환 wrapper. 내부에서는 canonical 모델을 검증한다."""
    unified = _structure_unified(
        text,
        doc_type,
        document_id=f"minimum-mvp-{doc_type}",
        routing_decisions=routing_decisions,
    )
    return document_to_legacy(unified)


def _read_and_structure(
    content: bytes,
    filename: str,
    doc_type: str,
    force_ocr: bool = False,
    budget: ExternalCallBudget | None = None,
) -> dict[str, Any]:
    """문서 1건 읽기·구조화. 한 문서 실패가 다른 문서를 막지 않는다."""
    try:
        text, method = extract_document_text(content, filename, force_ocr=force_ocr)
    except DocumentReadError as exc:
        return {"read_ok": False, "read_method": None, "error": str(exc)}
    if method == "vlm":
        mime = "application/pdf" if filename.lower().endswith(".pdf") else (
            "image/png" if filename.lower().endswith(".png") else "image/jpeg"
        )
        try:
            fields = extract_scanned_fields(
                content,
                mime,
                "contract" if doc_type == "contract" else "registry",
                budget=budget or ExternalCallBudget(),
            )
        except GeminiExtractError as exc:
            return {
                "read_ok": False,
                "read_method": "vlm",
                "error": f"스캔 문서 구조화에 실패했습니다: {exc} 수동 입력 또는 디지털 문서를 사용하세요.",
            }
        label = "contract" if doc_type == "contract" else "registry_record"
        legacy = LegacyDocumentExtraction(
            label,
            fields,
            [key for key, value in fields.items() if value is None],
        ).to_dict()
        doc = document_to_legacy(
            document_from_legacy(legacy, document_id=f"minimum-mvp-{doc_type}")
        )
        doc["read_method"] = "vlm"
        doc["read_ok"] = True
        return doc
    expected = "contract" if doc_type == "contract" else "registry"
    kind = _detect_doc_kind(text)
    if kind is not None and kind != expected:
        # 자리가 뒤바뀐 업로드 — 빈 추출값을 내보내는 대신 파일 확인을 안내한다.
        return {
            "read_ok": False,
            "read_method": method,
            "error": f"{_KIND_LABELS[expected]} 자리에 {_KIND_LABELS[kind]}로 보이는 문서가 올라왔습니다. "
            "계약서와 등기사항증명서를 맞게 선택했는지 확인해주세요.",
        }
    routing_decisions: list[RoutingDecision] = []
    doc = _structure(text, doc_type, routing_decisions=routing_decisions)
    doc["read_method"] = method  # 디지털 추출 vs OCR — UI 배지·투명성
    doc["read_ok"] = True
    doc["routing_decisions"] = [
        decision.to_dict() for decision in routing_decisions
    ]
    return doc


def extract_documents(
    contract_content: bytes,
    contract_filename: str,
    registry_content: bytes | None = None,
    registry_filename: str | None = None,
    force_ocr: bool = False,
) -> dict[str, Any]:
    for content in (contract_content, registry_content):
        if content is None:
            continue
        if len(content) > MAX_FILE_SIZE:
            raise ValueError("파일당 최대 크기는 최소 MVP에서 10MB입니다.")
    # 두 문서는 독립이지만 공유 호출 예산과 전역 동시성 제한을 지킨다.
    from concurrent.futures import ThreadPoolExecutor

    budget = ExternalCallBudget()
    with ThreadPoolExecutor(max_workers=2) as pool:
        contract_job = pool.submit(
            _read_and_structure, contract_content, contract_filename, "contract", force_ocr, budget
        )
        if registry_content is None or registry_filename is None:
            return {
                "contract": contract_job.result(),
                "registry": {
                    "document_type": "registry_record",
                    "fields": {},
                    "warnings": ["등기사항증명서가 없어 관련 항목은 확인 불가로 처리합니다."],
                    "read_method": None,
                    "read_ok": True,
                },
            }
        registry_job = pool.submit(
            _read_and_structure, registry_content, registry_filename, "registry", force_ocr, budget
        )
        return {"contract": contract_job.result(), "registry": registry_job.result()}


def analyze_verified_fields(
    contract_fields: dict[str, Any],
    registry_fields: dict[str, Any],
    contract_context: ContractContext,
) -> list[dict[str, Any]]:
    """legacy 확인 완료 입력을 canonical 스냅샷·분석 경로로 실행한다.

    이 호환 API는 최초값과 수정 이력을 따로 받지 않으므로 전달된 최종 필드를
    사용자가 확인한 effective value로 해석한다. 새 저장 API는 CorrectionRequest와
    DocumentExtraction 원본을 별도로 보존해야 한다.
    """
    contract_doc = confirm_document(
        document_from_legacy(
            {"document_type": "contract", "fields": contract_fields},
            document_id="minimum-mvp-contract",
        )
    )
    registry_doc = confirm_document(
        document_from_legacy(
            {"document_type": "registry_record", "fields": registry_fields},
            document_id="minimum-mvp-registry",
        )
    )
    snapshot = build_snapshot(
        input_snapshot_id="minimum-mvp-snapshot",
        contract_id=contract_context.contract_id,
        contract_context=contract_context,
        contract_doc=contract_doc,
        registry_doc=registry_doc,
        confirmed_at=datetime.now(timezone.utc),
    )
    analysis = analyze_snapshot(snapshot, analysis_run_id="minimum-mvp-analysis")
    return [result.model_dump(mode="json") for result in analysis.results]
