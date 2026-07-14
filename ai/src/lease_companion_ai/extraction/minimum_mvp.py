"""표준 계약서·등기사항증명서 텍스트용 결정론적 필드 파서."""

from __future__ import annotations

import re
from datetime import date

from lease_companion_ai.schemas.minimum_mvp import DocumentExtraction


_DATE = re.compile(r"(20\d{2})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일")
_VAGUE = ("협의", "추후", "상황에 따라", "적절히", "필요시")


def _first(patterns: tuple[str, ...], text: str, flags: int = 0) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags)
        if match:
            return match.group(1).strip(" \t:：/")
    return None


def _line_containing(text: str, *keywords: str) -> str | None:
    for line in text.splitlines():
        compact = line.strip()
        if compact and all(keyword in compact for keyword in keywords):
            return compact
    return None


def _clause_status(line: str | None, responsibility: bool = False) -> str:
    if not line:
        return "미기재"
    if any(word in line for word in _VAGUE):
        return "불명확"
    if responsibility:
        has_subject = "임대인" in line or "임차인" in line
        has_scope = any(word in line for word in ("수리", "수선", "원상복구", "파손", "설비"))
        return "명확" if has_subject and has_scope else "불명확"
    has_timing = any(word in line for word in ("종료", "인도", "퇴거", "동시", "반환일"))
    return "명확" if has_timing else "불명확"


def parse_contract(text: str) -> DocumentExtraction:
    property_address = _first(
        (
            r"(?:소재지|목적물\s*주소)\s*[:：]\s*([^\r\n]+)",
            r"부동산의\s*표시[^\r\n]*\r?\n\s*([^\r\n]+)",
        ),
        text,
    )
    landlord_name = _first(
        (
            r"임\s*대\s*인\s*[:：]\s*([가-힣A-Za-z0-9㈜()\s]+?)(?:\s*\(|\s*서명|\s*날인|\r?$)",
            r"임대인\s*(?:성명|이름)?\s*[:：]\s*([가-힣A-Za-z0-9㈜() ]+)",
        ),
        text,
        re.MULTILINE,
    )
    account_holder = _first(
        (r"(?:예금주|계좌\s*명의)\s*[:：]\s*([^/\r\n]+)",), text
    )
    return_line = _line_containing(text, "보증금", "반환")
    repair_line = next(
        (
            line.strip()
            for line in text.splitlines()
            if any(word in line for word in ("수리", "수선", "원상복구"))
            and any(subject in line for subject in ("임대인", "임차인"))
        ),
        None,
    )
    rights_line = next(
        (
            line.strip()
            for line in text.splitlines()
            if any(word in line for word in ("권리변동", "담보권", "근저당"))
            and any(word in line for word in ("설정하지", "제한", "금지", "동의"))
        ),
        None,
    )

    fields = {
        "landlord_name": landlord_name,
        "property_address": property_address,
        "account_holder": account_holder,
        "deposit_return_condition": _clause_status(return_line),
        "repair_responsibility": _clause_status(repair_line, responsibility=True),
        "rights_change_clause_present": rights_line is not None,
    }
    unconfirmed = [key for key, value in fields.items() if value is None]
    return DocumentExtraction("contract", fields, unconfirmed)


def _parse_date(text: str) -> str | None:
    match = _DATE.search(text)
    if not match:
        return None
    try:
        return date(*(int(part) for part in match.groups())).isoformat()
    except ValueError:
        return None


def _active_lines(text: str) -> list[str]:
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip() and "없음" not in line and "말소" not in line
    ]


def parse_registry(text: str) -> DocumentExtraction:
    property_address = _first(
        (
            r"(?:소재지번[^:：\r\n]*|소재지|부동산의\s*표시)\s*[:：]\s*([^\r\n]+)",
        ),
        text,
    )
    owner_names = re.findall(r"소유자\s+([가-힣A-Za-z0-9㈜()]+)", text)
    owner_names = list(dict.fromkeys(owner_names))
    issue_line = next(
        (line for line in text.splitlines() if "열람일시" in line or "발급일" in line), None
    )
    active = "\n".join(_active_lines(text))
    fields = {
        "owner_names": owner_names or None,
        "property_address": property_address,
        "issue_date": _parse_date(issue_line or ""),
        "mortgage_present": bool(re.search(r"근저당권(?:설정)?", active)),
        "seizure_present": bool(re.search(r"(?<!가)압류", active)),
        "provisional_seizure_present": "가압류" in active,
        "trust_present": bool(re.search(r"신탁(?:등기|원부)?", active)),
    }
    unconfirmed = [key for key, value in fields.items() if value is None]
    return DocumentExtraction("registry_record", fields, unconfirmed)
