"""표준 계약서·등기사항증명서 텍스트용 결정론적 필드 파서.

정규식 기반 **데모 스탠드인**이다. 실제 MVP 추출은 상용 LLM(Gemini 3.5 Flash)로
교체 예정(최종 모델·기술 선정표). 공백/콜론 표기 변형과 '(판독 불가)' 마커를
한 파서에서 함께 처리한다.
"""

from __future__ import annotations

import re
from datetime import date

from lease_companion_ai.schemas.minimum_mvp import DocumentExtraction


_DATE_KR = re.compile(r"(20\d{2})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일")
_DATE_NUM = re.compile(r"(20\d{2})[-./](\d{1,2})[-./](\d{1,2})")
_VAGUE = ("협의", "추후", "상황에 따라", "적절히", "필요시")
_UNREADABLE = ("판독", "불가")


def _unreadable(value: str | None) -> bool:
    return bool(value) and any(mark in value for mark in _UNREADABLE)


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


def _parse_date(text: str) -> str | None:
    match = _DATE_KR.search(text) or _DATE_NUM.search(text)
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


def _finalize(document_type: str, fields: dict) -> DocumentExtraction:
    """'(판독 불가)' 마커를 값으로 인정하지 않고, 미확인 필드를 재계산한다."""
    for key, value in list(fields.items()):
        if isinstance(value, str) and _unreadable(value):
            fields[key] = None
        elif isinstance(value, list):
            cleaned = [item for item in value if not _unreadable(item)]
            fields[key] = cleaned or None
    unconfirmed = [key for key, value in fields.items() if value is None]
    return DocumentExtraction(document_type, fields, unconfirmed)


def parse_contract(text: str) -> DocumentExtraction:
    property_address = _first(
        (
            r"(?:소재지|목적물\s*주소)\s*[:：]\s*([^\r\n]+)",
            r"목적물\s*[:：]\s*([^\r\n(]+)",
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
    account_holder = _first((r"(?:예금주|계좌\s*명의)\s*[:：]\s*([^/\r\n]+)",), text)
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
    return _finalize("contract", fields)


def parse_registry(text: str) -> DocumentExtraction:
    property_address = _first(
        (r"(?:소재지번[^:：\r\n]*|소재지|부동산의\s*표시)\s*[:：]\s*([^\r\n]+)",),
        text,
    )
    # 공백·콜론 표기 모두 허용: "소유자 홍길동" / "소유자: 홍길동"
    owner_names = re.findall(r"소유자\s*[:：]?\s*([가-힣A-Za-z0-9㈜()]+)", text)
    owner_names = list(dict.fromkeys(owner_names)) or None
    issue_line = next(
        (line for line in text.splitlines() if "열람" in line or "발급일" in line), ""
    )
    active = "\n".join(_active_lines(text))
    fields = {
        "owner_names": owner_names,
        "property_address": property_address,
        "issue_date": _parse_date(issue_line),
        "mortgage_present": bool(re.search(r"근저당권(?:설정)?", active)),
        "seizure_present": bool(re.search(r"(?<!가)압류", active)),
        "provisional_seizure_present": "가압류" in active,
        "trust_present": bool(re.search(r"신탁(?:등기|원부)?", active)),
    }
    result = _finalize("registry_record", fields)
    # 등기 전체 판독불가(소유자·소재지 모두 미확인)면 존재 플래그의 False는
    # "(읽고) 없음"이 아니라 "판독불가"다 → None으로 되돌려 규칙이 '확인 불가'를 내게 한다.
    # 개별 필드만 판독불가(예: 소유자만)면 나머지가 읽히므로 플래그 유지(무회귀).
    resolved = result.fields
    if resolved["owner_names"] is None and resolved["property_address"] is None:
        for key in ("mortgage_present", "seizure_present", "provisional_seizure_present", "trust_present"):
            if resolved[key] is False:
                resolved[key] = None
        result.unconfirmed_fields = [key for key, value in resolved.items() if value is None]
    return result
