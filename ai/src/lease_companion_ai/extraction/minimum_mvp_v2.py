"""최소 MVP 파서의 표기 변형 보정 계층."""

from __future__ import annotations

import re
from datetime import date

from lease_companion_ai.extraction.minimum_mvp import parse_contract as _parse_contract
from lease_companion_ai.extraction.minimum_mvp import parse_registry as _parse_registry
from lease_companion_ai.schemas.minimum_mvp import DocumentExtraction


def parse_contract(text: str) -> DocumentExtraction:
    extraction = _parse_contract(text)
    if not extraction.fields.get("property_address"):
        match = re.search(r"목적물\s*[:：]\s*([^\r\n(]+)", text)
        if match:
            extraction.fields["property_address"] = match.group(1).strip()
            extraction.unconfirmed_fields = [
                key for key in extraction.unconfirmed_fields if key != "property_address"
            ]
    return extraction


def parse_registry(text: str) -> DocumentExtraction:
    extraction = _parse_registry(text)
    if not extraction.fields.get("owner_names"):
        names = re.findall(r"소유자\s*[:：]\s*([가-힣A-Za-z0-9㈜()]+)", text)
        if names:
            extraction.fields["owner_names"] = list(dict.fromkeys(names))
            extraction.unconfirmed_fields = [
                key for key in extraction.unconfirmed_fields if key != "owner_names"
            ]
    if not extraction.fields.get("issue_date"):
        line = next(
            (value for value in text.splitlines() if "열람" in value or "발급일" in value),
            "",
        )
        match = re.search(r"(20\d{2})[-./](\d{1,2})[-./](\d{1,2})", line)
        if match:
            try:
                extraction.fields["issue_date"] = date(
                    *(int(part) for part in match.groups())
                ).isoformat()
                extraction.unconfirmed_fields = [
                    key for key in extraction.unconfirmed_fields if key != "issue_date"
                ]
            except ValueError:
                pass
    return extraction
