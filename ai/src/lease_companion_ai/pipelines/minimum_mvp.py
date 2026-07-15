"""최소 MVP의 인식·추출·규칙 실행 파이프라인."""

from __future__ import annotations

import re
from typing import Any

from lease_companion_ai.extraction.gemini_extractor import (
    GeminiExtractError,
    extract_contract_fields,
    extract_registry_fields,
)
from lease_companion_ai.extraction.minimum_mvp import parse_contract, parse_registry
from lease_companion_ai.ingestion.pdf_text import DocumentReadError, extract_document_text
from lease_companion_ai.rules.minimum_mvp import run_rules
from lease_companion_ai.schemas.minimum_mvp import DocumentExtraction


MAX_FILE_SIZE = 10 * 1024 * 1024

_KIND_LABELS = {"contract": "계약서", "registry": "등기사항증명서"}


def _detect_doc_kind(text: str) -> str | None:
    """문서 종류 추정. 확신 있는 구조 표지가 있을 때만 판정하고, 애매하면 None."""
    # PDF 텍스트 레이어는 제목이 "등 기 사 항 …"처럼 글자 간 공백으로 나온다 — 공백 제거 후 판정.
    compact = re.sub(r"\s+", "", text)
    if "등기사항" in compact and any(marker in compact for marker in ("표제부", "갑구", "을구")):
        return "registry"
    if "임대차" in compact and "계약" in compact:
        return "contract"
    return None


def _structure(text: str, doc_type: str) -> dict[str, Any]:
    """문서 텍스트 → 구조화 필드. 상용 LLM(Gemini) 우선, 실패 시 정규식 파서 폴백.

    폴백은 shim이 아니라 graceful degradation: 키 없음·API 실패 시에도 합성 .txt 데모가 동작.
    """
    label = "contract" if doc_type == "contract" else "registry_record"
    try:
        fields = extract_contract_fields(text) if doc_type == "contract" else extract_registry_fields(text)
        unconfirmed = [key for key, value in fields.items() if value is None]
        return DocumentExtraction(label, fields, unconfirmed).to_dict()
    except GeminiExtractError:
        parser = parse_contract if doc_type == "contract" else parse_registry
        return parser(text).to_dict()


def _read_and_structure(content: bytes, filename: str, doc_type: str, force_ocr: bool = False) -> dict[str, Any]:
    """문서 1건 읽기·구조화. 읽기/OCR 실패를 개별 격리 — 한 문서 실패가 다른 문서를 막지 않는다."""
    try:
        text, method = extract_document_text(content, filename, force_ocr=force_ocr)
    except DocumentReadError as exc:
        return {"read_ok": False, "read_method": None, "error": str(exc)}
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
    doc = _structure(text, doc_type)
    doc["read_method"] = method  # 디지털 추출 vs OCR — UI 배지·투명성
    doc["read_ok"] = True
    return doc


def extract_documents(contract_content: bytes, contract_filename: str, registry_content: bytes, registry_filename: str, force_ocr: bool = False) -> dict[str, Any]:
    for content in (contract_content, registry_content):
        if len(content) > MAX_FILE_SIZE:
            raise ValueError("파일당 최대 크기는 최소 MVP에서 10MB입니다.")
    # 두 문서는 독립 → 동시 처리. OCR·구조화가 각각 수십 초짜리 API 호출이라
    # 순차 실행은 스캔 입력에서 체감 2배 느리다. 실패 격리는 _read_and_structure 내부 그대로.
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=2) as pool:
        contract_job = pool.submit(_read_and_structure, contract_content, contract_filename, "contract", force_ocr)
        registry_job = pool.submit(_read_and_structure, registry_content, registry_filename, "registry", force_ocr)
        return {"contract": contract_job.result(), "registry": registry_job.result()}


def analyze_verified_fields(contract_fields: dict[str, Any], registry_fields: dict[str, Any]) -> list[dict[str, Any]]:
    return [result.to_dict() for result in run_rules(contract_fields, registry_fields)]
