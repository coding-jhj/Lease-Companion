"""판독 불가 표기를 값으로 오인하지 않도록 하는 최종 보정."""

from __future__ import annotations

from lease_companion_ai.extraction.minimum_mvp_v2 import parse_contract
from lease_companion_ai.extraction.minimum_mvp_v2 import parse_registry as _parse_registry
from lease_companion_ai.schemas.minimum_mvp import DocumentExtraction


def parse_registry(text: str) -> DocumentExtraction:
    extraction = _parse_registry(text)
    owners = extraction.fields.get("owner_names")
    if owners and any("판독" in owner or "불가" in owner for owner in owners):
        extraction.fields["owner_names"] = None
    address = extraction.fields.get("property_address")
    if address and ("판독" in address or "불가" in address):
        extraction.fields["property_address"] = None
    extraction.unconfirmed_fields = [
        key for key, value in extraction.fields.items() if value is None
    ]
    return extraction
