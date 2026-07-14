"""최소 MVP의 인식·추출·규칙 실행 파이프라인."""

from __future__ import annotations

from typing import Any

from lease_companion_ai.extraction.minimum_mvp import parse_contract, parse_registry
from lease_companion_ai.ingestion.pdf_text import extract_document_text
from lease_companion_ai.rules.minimum_mvp import run_rules


MAX_FILE_SIZE = 10 * 1024 * 1024


def extract_documents(contract_content: bytes, contract_filename: str, registry_content: bytes, registry_filename: str) -> dict[str, Any]:
    for content in (contract_content, registry_content):
        if len(content) > MAX_FILE_SIZE:
            raise ValueError("파일당 최대 크기는 최소 MVP에서 10MB입니다.")
    contract_text = extract_document_text(contract_content, contract_filename)
    registry_text = extract_document_text(registry_content, registry_filename)
    return {
        "contract": parse_contract(contract_text).to_dict(),
        "registry": parse_registry(registry_text).to_dict(),
    }


def analyze_verified_fields(contract_fields: dict[str, Any], registry_fields: dict[str, Any]) -> list[dict[str, Any]]:
    return [result.to_dict() for result in run_rules(contract_fields, registry_fields)]
