"""표준 계약서·등기사항증명서 텍스트용 결정론적 필드 파서.

정규식 기반 **데모 스탠드인**이다. 실제 MVP 추출은 상용 LLM(Gemini 3.5 Flash)로
교체 예정(최종 모델·기술 선정표). 공백/콜론 표기 변형과 '(판독 불가)' 마커를
한 파서에서 함께 처리한다.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date
from fractions import Fraction

from lease_companion_ai.schemas.minimum_mvp import DocumentExtraction


_DATE_KR = re.compile(r"(20\d{2})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일")
_DATE_NUM = re.compile(r"(20\d{2})[-./](\d{1,2})[-./](\d{1,2})")
_VAGUE = ("협의", "추후", "상황에 따라", "적절히", "필요시")
_UNREADABLE = ("판독", "불가")
_OWNER_NAME = r"[가-힣A-Za-z0-9㈜()]+"
_PERSON_NAME = r"[가-힣A-Za-z㈜()]{2,30}"
_ADDRESS_MARKERS = ("시", "도", "구", "군", "읍", "면", "동", "리", "로", "길")
_NON_NAME_VALUES = {"주소", "주민등록번호", "전화", "성명", "서명", "날인"}
_ADDRESS_TRAILING_FIELD = re.compile(
    r"\s+(?=(?:건물\s*내역|등기원인(?:\s*및)?\s*기타사항|기타\s*사항|"
    r"구조[·ㆍ]?용도|면적\s*[:：]?|철근콘크리트|벽돌조|블록조|목조|"
    r"시멘트|세멘|\d+(?:\.\d+)?\s*㎡|20\d{2}\s*년))"
)
_ADDRESS_LEADING_LABEL = re.compile(
    r"^\s*(?:(?:소\s*재\s*지|목적물\s*주소)\s*[:：]?\s*)?"
    r"(?:[\[(]\s*도로명주소\s*[\])]|도로명주소\s*[:：]?)\s*"
)
_REGISTRY_DOCUMENT_NUMBER = re.compile(r"^\s*제\s*\d+\s*호\s*")
_REGISTRY_TRAILING_EFFECT = re.compile(
    r"\s+\d+\s*층\s+\d+(?:\.\d+)?(?:\s*㎡)?\s*효력(?:\s.*)?$"
)
_KOREAN_DIGITS = {
    "일": 1,
    "이": 2,
    "삼": 3,
    "사": 4,
    "오": 5,
    "육": 6,
    "칠": 7,
    "팔": 8,
    "구": 9,
}
_KOREAN_SMALL_UNITS = {"십": 10, "백": 100, "천": 1_000}
_KOREAN_LARGE_UNITS = {"만": 10_000, "억": 100_000_000, "조": 1_000_000_000_000}


def _unreadable(value: str | None) -> bool:
    if value is None:
        return False
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


def _normalize_extraction_text(text: str) -> str:
    """PDF 글꼴·공백 변형을 통일하되 표의 줄 경계는 유지한다."""
    normalized = unicodedata.normalize("NFKC", text).replace("\u00a0", " ")
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(
        re.sub(r"[ \t]+", " ", line).strip() for line in normalized.splitlines()
    )


def _looks_like_address(value: str) -> bool:
    return bool(re.search(r"\d", value)) and any(
        marker in value for marker in _ADDRESS_MARKERS
    )

def _clean_address_candidate(value: str) -> str:
    """PDF 표의 같은 행에 붙은 문서번호·표시 라벨·기타 셀을 주소에서 제외한다."""
    value = _REGISTRY_DOCUMENT_NUMBER.sub("", value, count=1)
    value = _ADDRESS_LEADING_LABEL.sub("", value, count=1)
    value = _ADDRESS_TRAILING_FIELD.split(value, maxsplit=1)[0]
    value = _REGISTRY_TRAILING_EFFECT.sub("", value, count=1)
    value = re.split(
        r"\s*[·ㆍ]\s*(?=(?:전용면적|공급면적|공동주택|구조|용도))",
        value,
        maxsplit=1,
    )[0]
    return value.strip(" \t:：─-")



def _address_near_label(text: str, label_pattern: str, lookahead: int = 6) -> str | None:
    """표 머리글과 실제 주소가 다른 줄에 있어도 가까운 주소 행을 찾는다."""
    lines = text.splitlines()
    label = re.compile(label_pattern)
    for index, line in enumerate(lines):
        match = label.search(line)
        if not match:
            continue
        same_line = _clean_address_candidate(line[match.end() :])
        if _looks_like_address(same_line):
            return same_line
        for candidate in lines[index + 1 : index + 1 + lookahead]:
            candidate = _clean_address_candidate(candidate)
            if _looks_like_address(candidate):
                return candidate
    return None

def _extract_contract_address(text: str) -> str | None:
    return _address_near_label(
        text,
        r"(?:소\s*재\s*지|목적물\s*주소|임대\s*목적물|임차주택의\s*표시)",
    ) or _first(
        (
            r"(?:소\s*재\s*지|목적물\s*주소)\s*[:：]?\s*(?:\n\s*)?([^\n]+)",
            r"(?:임차주택|부동산)의\s*표시[^\n]*(?:\n\s*)+"
            r"(?:소\s*재\s*지\s*[:：]?\s*(?:\n\s*)+)?([^\n]+)",
            r"목적물\s*[:：]\s*([^\n(]+)",
        ),
        text,
    )


def _standalone_name_near_signature(block: str) -> str | None:
    """임대인 표에서 성명·서명 셀 주변의 독립된 이름 행을 찾는다."""
    lines = block.splitlines()
    anchors = [
        index
        for index, line in enumerate(lines)
        if re.search(r"성\s*명|서명|날인", line)
    ]
    for distance in range(5):
        for anchor in anchors:
            for index in dict.fromkeys((anchor + distance, anchor - distance)):
                if index < 0 or index >= len(lines):
                    continue
                candidate = re.sub(r"\([^)]*(?:서명|날인)[^)]*\)", " ", lines[index])
                candidate = re.sub(r"\(\s*인\s*\)", " ", candidate)
                candidate = re.sub(r"성\s*명\s*[:：]?", " ", candidate)
                candidate = re.sub(r"\s+", "", candidate).strip(" :：")
                if (
                    re.fullmatch(_PERSON_NAME, candidate)
                    and candidate not in _NON_NAME_VALUES
                ):
                    return candidate
    return None


def _extract_party_name(text: str, role: str, block_end: str) -> str | None:
    spaced_role = r"\s*".join(role)
    direct = _first(
        (
            rf"{spaced_role}(?:\s*\([^\n)]*\))?\s*[:：]?\s*"
            r"(?:\n\s*)?(?:성\s*명\s*[:：]?\s*(?:\n\s*)?)?"
            r"([가-힣A-Za-z0-9㈜()]{2,30})(?=\s*(?:\(|서명|날인|\n|$))",
            rf"{role}\s*(?:성명|이름)\s*[:：]?\s*"
            r"(?:\n\s*)?([가-힣A-Za-z0-9㈜()]{2,30})",
        ),
        text,
        re.MULTILINE,
    )
    if direct and direct not in _NON_NAME_VALUES:
        return direct
    # 본문 서두("임대인과 임차인은…")처럼 이름 없는 언급을 건너뛰고, 이름이 나오는 첫 구획을 쓴다.
    for party_block in re.finditer(
        rf"{spaced_role}(?P<body>.*?)(?={block_end}|\Z)", text, re.DOTALL
    ):
        block = party_block.group("body")
        explicit = _first(
            (
                rf"성\s*명\s*[:：]?\s*(?:\n\s*)?({_PERSON_NAME})(?=\s*(?:\(|서명|날인|\n|$))",
                rf"(?:성명|이름)\s*[:：]?\s*(?:\n\s*)?({_PERSON_NAME})",
            ),
            block,
            re.MULTILINE,
        )
        name = explicit or _standalone_name_near_signature(block)
        if name:
            return name
    return None


def _extract_account_holder(text: str) -> str | None:
    return _first(
        (
            rf"예\s*금\s*주\s*[:：]?\s*(?:\n\s*)?({_PERSON_NAME})(?=\s*(?:/|\||\n|$))",
            rf"계좌\s*(?:명의|예금주)\s*[:：]?\s*(?:\n\s*)?({_PERSON_NAME})",
            rf"입금\s*계좌\s*명의\s*[:：]?\s*(?:\n\s*)?({_PERSON_NAME})",
        ),
        text,
        re.MULTILINE,
    )


def _extract_bank_name(text: str) -> str | None:
    # 예금주와 독립. 은행명은 계좌·입금 문맥 유무와 무관하게 은행 어휘 자체로 잡는다.
    return _first(
        (
            r"([가-힣]{2,10}(?:은행|농협|수협|신협|새마을금고))",
            r"(카카오뱅크|케이뱅크|토스뱅크)",
        ),
        text,
    )


def _extract_account_number(text: str) -> str | None:
    # 예금주 미기재라도 계좌번호는 따로 추출한다. 내부 공백은 제거하고 하이픈은 보존.
    raw = _first(
        (
            r"계\s*좌\s*(?:번호)?\s*[:：]?\s*((?:\d[\d\-\s]{7,})\d)",
            r"입금\s*계좌\s*[:：]?\s*(?:[가-힣]{2,10}은행\s*)?((?:\d[\d\-\s]{7,})\d)",
            r"(\d{2,6}-\d{2,6}-\d{2,7})",
        ),
        text,
    )
    return re.sub(r"\s+", "", raw) if raw else None


def _contract_type(text: str) -> str | None:
    compact = re.sub(r"\s+", "", text)
    checked_monthly = bool(re.search(r"(?:☑|■|●|✓)월세", compact))
    if checked_monthly:
        deposit_line = _money_line(text, r"보\s*증\s*금")
        return "보증부월세" if (_numeric_money(deposit_line) or 0) > 0 else "일반월세"
    for marker, value in (
        ("☑보증금있는월세", "보증부월세"),
        ("☑전세", "전세"),
    ):
        if marker in compact:
            return value
    for marker in ("보증부월세", "일반월세", "전세"):
        if marker in compact:
            return marker
    return None


def _money_line(text: str, pattern: str) -> str | None:
    label = re.compile(pattern)
    for line in text.splitlines():
        match = label.search(line)
        has_amount = (
            "₩" in line
            or bool(re.search(r"\d+\s*(?:만|억)?\s*원", line))
            or bool(
                re.search(
                    r"(?:^|\s)금\s*[일이삼사오육칠팔구십백천만억조]+\s*원",
                    line,
                )
            )
        )
        if match and has_amount:
            return line[match.start() :].strip()
    return None


def _numeric_money(line: str | None) -> int | None:
    if not line or _unreadable(line):
        return None
    won = re.search(r"₩\s*([\d,]+)", line)
    if won:
        return int(won.group(1).replace(",", ""))
    amount = re.search(r"(?<![\d,])(\d[\d,]*(?:\.\d+)?)\s*(억|만)?\s*원", line)
    if not amount:
        return None
    multiplier = {None: 1, "만": 10_000, "억": 100_000_000}[amount.group(2)]
    return int(float(amount.group(1).replace(",", "")) * multiplier)


def _korean_money(line: str | None) -> int | None:
    if not line or _unreadable(line):
        return None
    match = re.search(
        r"(?:^|\s)금\s*([일이삼사오육칠팔구십백천만억조]+)\s*원(?:정)?",
        line,
    )
    if not match:
        return None
    total = 0
    section = 0
    number = 0
    for character in match.group(1):
        if character in _KOREAN_DIGITS:
            number = _KOREAN_DIGITS[character]
        elif character in _KOREAN_SMALL_UNITS:
            section += (number or 1) * _KOREAN_SMALL_UNITS[character]
            number = 0
        else:
            section += number
            total += (section or 1) * _KOREAN_LARGE_UNITS[character]
            section = 0
            number = 0
    return total + section + number


def _dates(text: str) -> list[str]:
    found: list[tuple[int, str]] = []
    for pattern in (_DATE_KR, _DATE_NUM):
        for match in pattern.finditer(text):
            parsed = _parse_date(match.group(0))
            if parsed is not None:
                found.append((match.start(), parsed))
    return [value for _, value in sorted(found)]


def _line_matching(text: str, pattern: str) -> str | None:
    expression = re.compile(pattern)
    return next(
        (line.strip() for line in text.splitlines() if expression.search(line)),
        None,
    )


def _agent_fields(text: str) -> tuple[str | None, str | None, list[str] | None]:
    agent_name = _first(
        (
            r"대리인\s*[:：]\s*([가-힣A-Za-z㈜]{2,30})",
            r"의\s+대리인\s+([가-힣A-Za-z㈜]{2,30})",
        ),
        text,
    )
    relationship = _first(
        (
            r"관계\s*[:：]\s*([^\n)]+)",
            r"대리인\s*[:：]\s*[^\n(]+\((임대인\s*위임)\)",
        ),
        text,
    )
    if agent_name is None:
        return None, None, None
    documents = [
        document
        for document in ("위임장", "인감증명서", "본인서명사실확인서")
        if document in text
    ]
    return agent_name, relationship, documents or None


def _building_use(text: str) -> str | None:
    """임차주택 표시의 구조·용도 행에서 용도만 보수적으로 읽는다."""
    known_uses = (
        "다가구주택",
        "다세대주택",
        "단독주택",
        "연립주택",
        "공동주택",
        "주거용 오피스텔",
        "오피스텔",
        "아파트",
    )
    for line in text.splitlines():
        if not re.search(r"구조\s*[·ㆍ/]?\s*용도|건축물\s*용도", line):
            continue
        compact = re.sub(r"\s+", "", line)
        for usage in known_uses:
            if re.sub(r"\s+", "", usage) in compact:
                return usage
        # PyMuPDF 표 정렬이 '오피스텔' 사이에 다른 열을 끼워 넣는 경우.
        if "오피스" in compact and compact.rfind("텔") > compact.find("오피스"):
            return "오피스텔"
    return None


def _contract_execution_date(text: str) -> str | None:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if re.search(r"계약\s*(?:체결)?일|본\s*계약을\s*증명", line):
            # 표준 PDF는 서명 문장의 날짜가 폭 때문에 바로 다음 줄로 넘어갈 수 있다.
            dates = _dates(" ".join(lines[index : index + 2]))
            if dates:
                return dates[-1]
    return None


def _move_in_date(text: str) -> str | None:
    for line in text.splitlines():
        if re.search(r"입주(?:일)?", line) and not re.search(r"입주일\s*(?:전날|전일|이전)", line):
            parsed = _parse_date(line)
            if parsed:
                return parsed
    # 표준계약서 제2조는 입주일 대신 임차주택 인도일을 기재한다.
    for line in text.splitlines():
        if "인도" in line and "임차인" in line:
            dates = _dates(line)
            if dates:
                return dates[0]
    return None


def _management_fields(
    text: str,
) -> tuple[bool | None, int | None, list[str] | None]:
    candidates = [line.strip() for line in text.splitlines() if re.search(r"관리\s*비", line)]
    line = next(
        (
            candidate
            for candidate in candidates
            if not re.search(r"제\s*\d+\s*조", candidate)
            and (
                "없음" in candidate
                or "원" in candidate
                or "비례" in candidate
                or "포함" in candidate
                or "별도" in candidate
            )
        ),
        candidates[0] if candidates else None,
    )
    if line is None:
        return False, None, None
    if _unreadable(line):
        return None, None, None
    if "없음" in line or re.search(r"관리\s*비(?:는|가)?\s*없", line):
        return False, None, None
    items: list[str] | None = None
    groups = [
        group
        for group in re.findall(r"\(([^)]+)\)", line)
        if "정액이 아닌 경우" not in group and group.strip() != "관리비"
    ]
    if groups:
        values = "·".join(re.sub(r"\s*포함\s*$", "", group) for group in groups)
        items = [item.strip() for item in re.split(r"[·ㆍ,/]|\s+및\s+", values) if item.strip()] or None
    return True, _numeric_money(line), items


def _clause_sections(
    text: str,
) -> tuple[list[str] | None, bool, list[str] | None]:
    lines = text.splitlines()
    special_index = next(
        (index for index, line in enumerate(lines) if "특약사항" in line),
        None,
    )
    boundary = special_index if special_index is not None else len(lines)
    main = [
        line.strip()
        for line in lines[:boundary]
        if line.strip()
        and (
            re.search(r"제\s*\d+\s*조", line)
            or re.search(r"\[(?:가|제\s*\d+\s*항)\]", line)
            or "임대차기간" in line
        )
    ]
    if special_index is None:
        return main or None, False, None
    header = lines[special_index]
    following = next(
        (line.strip() for line in lines[special_index + 1 :] if line.strip()),
        "",
    )
    if "없음" in header or following in {"없음", "(없음)", "기재 사항 없음"}:
        return main or None, False, None
    special: list[str] = []
    bullet = re.compile(r"^[-·ㆍ•▪◦]\s*")
    for line in lines[special_index + 1 :]:
        stripped = line.strip()
        if not stripped:
            if special:
                break
            continue
        if re.match(r"\d+\.\s+", stripped):
            break
        if bullet.match(stripped):
            special.append(stripped)
        elif special:
            # PDF 텍스트 레이어에서 한 특약 문장이 다음 줄로 잘린 경우 이전 항목에 잇는다.
            special[-1] = f"{special[-1]} {stripped}"
    return main or None, True, special or None





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


def _ownership_section(text: str) -> str:
    """갑구 본문만 반환한다. 을구 권리자 이름을 소유자로 오인하지 않는다."""
    match = re.search(
        r"(?:\[|【)?갑구(?:\]|】)?(?P<body>.*?)(?=(?:\[|【)?을구(?:\]|】)?|\Z)",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    return match.group("body") if match else text


# PDF 표 추출(sort=True)이 '효력' 열 셀·다음 순위 행을 앞 행 끝에 이어붙이는 경우,
# 줄 중간의 "순위번호 + 등기목적" 앞에서 줄을 갈라 행 경계를 복원한다.
_MIDLINE_RANK = re.compile(
    r"[ \t]+(?=\d+(?:-\d+)?[ \t]+(?:소유권|공유자|등기명의인|말소|경정|변경|압류|가압류|신탁|경매))"
)


def _ranked_ownership_entries(section: str) -> tuple[list[tuple[str, str]], str]:
    """순위번호 단위로 갑구를 분리한다. (항목 목록, 첫 항목 이전의 앞부분) 반환."""
    section = _MIDLINE_RANK.sub("\n", section)
    pattern = re.compile(
        r"(?m)^[ \t]*(?:순위번호\s*)?(\d+(?:-\d+)?)\s+"
        r"(?=[^\r\n]*(?:소유권|공유자|등기명의인|말소|경정|변경|압류|신탁|경매))"
    )
    matches = list(pattern.finditer(section))
    entries = [
        (
            match.group(1),
            section[
                match.end() : matches[index + 1].start()
                if index + 1 < len(matches)
                else len(section)
            ].strip(),
        )
        for index, match in enumerate(matches)
    ]
    prefix = section[: matches[0].start()] if matches else ""
    return entries, prefix


def _parse_share(text: str) -> Fraction | None:
    korean = re.search(r"(?:지분\s*)?(\d+)\s*분의\s*(\d+)", text)
    if korean:
        denominator, numerator = (int(value) for value in korean.groups())
        return Fraction(numerator, denominator) if denominator else None
    slash = re.search(r"(?:지분\s*)?(\d+)\s*/\s*(\d+)", text)
    if slash:
        numerator, denominator = (int(value) for value in slash.groups())
        return Fraction(numerator, denominator) if denominator else None
    return None


def _holders(text: str) -> list[tuple[str, Fraction | None]]:
    holders: list[tuple[str, Fraction | None]] = []
    for line in text.splitlines():
        match = re.search(rf"(?:소유자|권리자)\s*[:：]?\s*({_OWNER_NAME})", line)
        if not match:
            continue
        name = match.group(1)
        if name in {"및", "성명", "이름"} or _unreadable(name):
            continue
        holders.append((name, _parse_share(line) if "지분" in line else None))
    return list(dict.fromkeys(holders))


def _cancelled_ranks(entries: list[tuple[str, str]]) -> tuple[set[str], bool]:
    cancelled: set[str] = set()
    complete = True
    for _, body in entries:
        first_line = body.splitlines()[0] if body else ""
        if "말소" not in first_line:
            continue
        reference = re.search(r"(\d+(?:-\d+)?)번[^\r\n]{0,40}말소", first_line)
        if reference:
            cancelled.add(reference.group(1))
        else:
            complete = False
    return cancelled, complete


def _apply_partial_transfer(
    state: dict[str, Fraction | None], body: str
) -> bool:
    """명시적인 양도인·양수인·지분을 읽을 수 있을 때만 일부 이전을 적용한다."""
    transferor_match = re.search(
        rf"(?:공유자|양도인)\s*[:：]?\s*({_OWNER_NAME})", body
    )
    if not transferor_match:
        return False
    transferor = transferor_match.group(1)
    transferor_share = state.get(transferor)
    if transferor_share is None:
        return False

    recipients = [(name, share) for name, share in _holders(body) if name != transferor]
    if len(recipients) != 1:
        return False
    recipient, recipient_share = recipients[0]

    amount_match = re.search(
        r"중\s*((?:\d+\s*분의\s*\d+)|(?:\d+\s*/\s*\d+))\s*(?:지분\s*)?이전",
        body,
    )
    amount = _parse_share(amount_match.group(1)) if amount_match else None
    if amount is None and "전부이전" in body:
        amount = transferor_share
    if amount is None or amount <= 0 or amount > transferor_share:
        return False
    if recipient_share is not None and recipient_share != amount:
        return False

    remaining = transferor_share - amount
    if remaining:
        state[transferor] = remaining
    else:
        state.pop(transferor)
    existing = state.get(recipient)
    state[recipient] = amount if existing is None else existing + amount
    return True


def _apply_owner_change(state: dict[str, Fraction | None], body: str) -> bool:
    """명시적인 이름 경정은 반영하고 주소 변경은 소유 상태를 유지한다."""
    rename = re.search(
        rf"(?:소유자|권리자)\s*[:：]?\s*({_OWNER_NAME})\s*(?:을|를|에서)\s*"
        rf"({_OWNER_NAME})\s*(?:으로|로)\s*(?:경정|변경)",
        body,
    )
    if rename:
        old_name, new_name = rename.groups()
        if old_name not in state:
            return False
        share = state.pop(old_name)
        existing_share = state.get(new_name)
        if existing_share is not None and share is not None:
            state[new_name] = existing_share + share
        else:
            state[new_name] = share
        return True
    return "주소" in body and bool(state)


def _current_owners(
    text: str,
) -> tuple[dict[str, Fraction | None] | None, list[str]]:
    """갑구 사건을 적용해 현재 소유자별 지분과 안전 경고를 반환한다."""
    section = _ownership_section(text)
    entries, prefix = _ranked_ownership_entries(section)
    if entries and _holders(prefix):
        # 순위 항목으로 잡히지 않은 구간에 소유자·권리자가 남아 있다 = 행 분리 실패.
        # 일부 이력만으로 확정하면 과거 소유자를 현재로 오판할 수 있어 확정하지 않는다.
        return None, [
            "소유권 사건 일부를 읽지 못했습니다. 현재 소유자를 직접 확인하세요."
        ]
    if not entries:
        holders = _holders(section)
        if len(holders) <= 1:
            if not holders:
                return None, []
            name, share = holders[0]
            return {name: share or Fraction(1, 1)}, []
        return (
            None,
            ["소유권 사건의 순서를 읽지 못했습니다. 현재 소유자를 직접 확인하세요."],
        )

    cancelled, complete = _cancelled_ranks(entries)
    state: dict[str, Fraction | None] = {}
    resolved = False
    warnings: list[str] = []

    for rank, body in entries:
        first_line = body.splitlines()[0] if body else ""
        if rank in cancelled or "말소" in first_line:
            continue

        if "지분" in first_line or "일부이전" in first_line:
            if not resolved or not _apply_partial_transfer(state, body):
                resolved = False
                complete = False
            continue

        if (
            "경정" in first_line
            or "변경" in first_line
            or "등기명의인" in first_line
        ):
            if not resolved or not _apply_owner_change(state, body):
                resolved = False
                complete = False
            continue

        if "소유권보존" in first_line or "소유권이전" in first_line:
            holders = _holders(body)
            if not holders:
                state = {}
                resolved = False
                continue
            if len(holders) == 1 and holders[0][1] is None:
                holders = [(holders[0][0], Fraction(1, 1))]
            state = dict(holders)
            resolved = True

    if not complete or not resolved or not state:
        warnings.append(
            "갑구 소유권 이력을 자동으로 확정하지 못했습니다. 현재 소유자를 직접 확인하세요."
        )
        return None, warnings
    return state, warnings


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
    text = _normalize_extraction_text(text)
    property_address = _extract_contract_address(text)
    landlord_name = _extract_party_name(text, "임대인", r"임\s*차\s*인|중\s*개")
    tenant_name = _extract_party_name(text, "임차인", r"임\s*대\s*인|중\s*개")
    account_holder = _extract_account_holder(text)
    account_number = _extract_account_number(text)
    bank_name = _extract_bank_name(text)
    agent_name, agent_relationship, proxy_documents = _agent_fields(text)
    building_use = _building_use(text)
    deposit_line = _money_line(text, r"보\s*증\s*금")
    rent_line = _money_line(text, r"(?:월\s*차임|차\s*임|월세)")
    contract_payment_line = _money_line(text, r"계\s*약\s*금")
    balance_payment_line = _money_line(text, r"잔\s*금")
    contract_payment_date = _parse_date(contract_payment_line or "")
    if (
        contract_payment_date is None
        and contract_payment_line is not None
        and re.search(r"계약\s*시(?:에)?", contract_payment_line)
    ):
        contract_payment_date = _contract_execution_date(text)
    period_lines = text.splitlines()
    period_index = next(
        (
            index
            for index, line in enumerate(period_lines)
            if re.search(r"(?:존속\s*기간|임대차\s*기간|\]\s*기간)", line)
        ),
        None,
    )
    period_parts: list[str] = []
    if period_index is not None:
        for line in period_lines[period_index : period_index + 3]:
            stripped = line.strip()
            if period_parts and re.match(r"제\s*\d+\s*조", stripped):
                break
            if stripped:
                period_parts.append(stripped)
    period_dates = _dates(" ".join(period_parts))
    management_present, management_fee, management_items = _management_fields(text)
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
    main_clauses, special_present, special_clauses = _clause_sections(text)

    fields = {
        "contract_type": _contract_type(text),
        "landlord_name": landlord_name,
        "tenant_name": tenant_name,
        "agent_name": agent_name,
        "agent_relationship": agent_relationship,
        "proxy_authority_documents": proxy_documents,
        "property_address": property_address,
        "building_use": building_use,
        "deposit": _numeric_money(deposit_line),
        "deposit_korean_amount": _korean_money(deposit_line),
        "monthly_rent": _numeric_money(rent_line),
        "monthly_rent_korean_amount": _korean_money(rent_line),
        "contract_payment": _numeric_money(contract_payment_line),
        "contract_payment_korean_amount": _korean_money(contract_payment_line),
        "balance_payment": _numeric_money(balance_payment_line),
        "balance_payment_korean_amount": _korean_money(balance_payment_line),
        "contract_payment_date": contract_payment_date,
        "balance_payment_date": _parse_date(balance_payment_line or ""),
        "move_in_date": _move_in_date(text),
        "start_date": period_dates[0] if period_dates else None,
        "end_date": period_dates[1] if len(period_dates) > 1 else None,
        "management_fee_present": management_present,
        "management_fee": management_fee,
        "management_fee_items": management_items,
        "account_holder": account_holder,
        "account_number": account_number,
        "bank_name": bank_name,
        "deposit_return_condition": _clause_status(return_line),
        "deposit_return_clause": return_line,
        "repair_responsibility": _clause_status(repair_line, responsibility=True),
        "repair_responsibility_clause": repair_line,
        "rights_change_clause_present": rights_line is not None,
        "main_clauses": main_clauses,
        "special_clauses_present": special_present,
        "special_clauses": special_clauses,
    }
    return _finalize("contract", fields)


def parse_registry(text: str) -> DocumentExtraction:
    text = _normalize_extraction_text(text)
    property_address = _address_near_label(
        text,
        r"(?:소\s*재\s*지\s*번(?:\s*[·,]\s*건물명칭\s*및\s*번호)?|소\s*재\s*지|부동산\s*(?:의\s*)?표시)",
        lookahead=10,
    ) or _first(
        (r"(?:소재지번[^:：\r\n]*|소재지|부동산\s*(?:의\s*)?표시)\s*[:：]\s*([^\r\n]+)",),
        text,
    )
    owners, ownership_warnings = _current_owners(text)
    owner_names = list(owners) if owners is not None else None
    owner_shares = (
        {
            name: f"{share.numerator}/{share.denominator}"
            for name, share in owners.items()
            if share is not None
        }
        if owners is not None and all(share is not None for share in owners.values())
        else None
    )
    issue_line = next(
        (line for line in text.splitlines() if "발급일" in line),
        next((line for line in text.splitlines() if "열람" in line), ""),
    )
    active = "\n".join(_active_lines(text))
    fields = {
        "owner_names": owner_names,
        "is_joint_ownership": len(owner_names) > 1 if owner_names is not None else None,
        "owner_shares": owner_shares,
        "property_address": property_address,
        "issue_date": _parse_date(issue_line),
        "mortgage_present": bool(re.search(r"근저당권(?:설정)?", active)),
        "seizure_present": bool(re.search(r"(?<!가)압류", active)),
        "provisional_seizure_present": "가압류" in active,
        "trust_present": bool(re.search(r"신탁(?:등기|원부)?", active)),
        "ground_right_present": bool(re.search(r"지상권(?:설정)?", active)),
    }
    result = _finalize("registry_record", fields)
    result.warnings.extend(ownership_warnings)
    # 등기 전체 판독불가(소유자·소재지 모두 미확인)면 존재 플래그의 False는
    # "(읽고) 없음"이 아니라 "판독불가"다 → None으로 되돌려 규칙이 '확인 불가'를 내게 한다.
    # 개별 필드만 판독불가(예: 소유자만)면 나머지가 읽히므로 플래그 유지(무회귀).
    resolved = result.fields
    if resolved["owner_names"] is None and resolved["property_address"] is None:
        for key in (
            "mortgage_present",
            "seizure_present",
            "provisional_seizure_present",
            "trust_present",
            "ground_right_present",
        ):
            if resolved[key] is False:
                resolved[key] = None
        result.unconfirmed_fields = [key for key, value in resolved.items() if value is None]
    return result
