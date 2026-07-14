"""최소 MVP의 인식·추출·규칙 실행 파이프라인."""

from __future__ import annotations

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


def _read_and_structure(content: bytes, filename: str, doc_type: str) -> dict[str, Any]:
    """문서 1건 읽기·구조화. 읽기/OCR 실패를 개별 격리 — 한 문서 실패가 다른 문서를 막지 않는다."""
    try:
        text, method = extract_document_text(content, filename)
    except DocumentReadError as exc:
        return {"read_ok": False, "read_method": None, "error": str(exc)}
    doc = _structure(text, doc_type)
    doc["read_method"] = method  # 디지털 추출 vs OCR — UI 배지·투명성
    doc["read_ok"] = True
    return doc


def extract_documents(contract_content: bytes, contract_filename: str, registry_content: bytes, registry_filename: str) -> dict[str, Any]:
    for content in (contract_content, registry_content):
        if len(content) > MAX_FILE_SIZE:
            raise ValueError("파일당 최대 크기는 최소 MVP에서 10MB입니다.")
    return {
        "contract": _read_and_structure(contract_content, contract_filename, "contract"),
        "registry": _read_and_structure(registry_content, registry_filename, "registry"),
    }


def analyze_verified_fields(contract_fields: dict[str, Any], registry_fields: dict[str, Any]) -> list[dict[str, Any]]:
    return [result.to_dict() for result in run_rules(contract_fields, registry_fields)]
