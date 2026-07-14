"""합성 데이터 생성기 — 케이스 파라미터 1개 → 5개 산출물 결정적 도출.

산출물: 계약서 .txt · 등기부 .txt · extraction/rule/rag goldset.
케이스 스펙(파라미터)이 단일 진실원천(single source of truth)이라
문서와 goldset 사이 라벨 드리프트가 원천적으로 불가능하다.

- 파일럿 5쌍(CASE-001~005, 손작성)은 보존하고 CASE-006~030(생성) 추가 = dev 30쌍.
- 테스트 10쌍(TEST-001~010)은 **전용 템플릿·전용 엔티티 풀**로 표면형을 분리(누수 차단),
  data/evaluation/end-to-end/ 로 별도 출력.
- 규칙·근거 goldset은 생성기가 도출(deterministic). 추출 현실성은 파일럿+OCR변형이 담당.

실행: python data/gen_dataset.py   (파일 생성 + 도출로직 self-check)
검증: python data/check_dataset.py

ponytail: 생성 계약서는 ₩숫자 금액만 사용(한글 금액 없음). J07(금액 표기 일치)는
R01–R10 범위 밖이라 한글 금액 변환기 불필요. 파일럿은 한글 금액 realism 유지.
"""
import csv
import hashlib
import json
import os

BASE = os.path.dirname(os.path.abspath(__file__))
SAMPLE = os.path.join(BASE, "sample")
E2E = os.path.join(BASE, "evaluation", "end-to-end")

# ── 결과 상태 분류 ────────────────────────────────────────────────
CLEAN = {"일치", "명확", "적용 제외"}                 # 비해당
FIRED = {"불일치", "확인 필요", "불명확", "미기재", "상충 가능"}  # 해당
# "확인 불가"는 분석불가(별도 버킷)

# ── 근거 매핑 로드 (rule_evidence_map = 단일 진실원천) ──────────────
def load_evidence_map():
    m = {}
    with open(os.path.join(BASE, "rules", "rule_evidence_map.csv"), encoding="utf-8") as f:
        for row in csv.DictReader(f):
            m.setdefault(row["rule_id"], []).append(row["source_id"])
    return m

EVID = load_evidence_map()

# ── 엔티티 풀 (dev/test 분리 — 누수 차단) ─────────────────────────
DEV_SUR = list("김이박최정강조윤장임한오서신권황안송류전")
DEV_GIV = ["지훈", "서연", "도현", "하은", "민준", "수아", "예준", "지우", "시우", "하준",
           "주원", "지호", "건우", "서준", "유진", "다은", "채원", "나윤", "소율", "가온"]
DEV_GU = ["새록구", "여울구", "라온구", "다솔구", "윤슬구", "벼리구", "아라구", "나린구",
          "단오구", "미리내구", "너울구", "가람구", "온다구", "예솔구", "빛가람구"]
DEV_RO = ["바람로", "슬기로", "꽃내로", "너른로", "푸른로", "달빛로", "별빛로", "이든로",
          "하랑로", "온새미로", "라온로", "가온로", "미르로", "노을로"]
# test 전용 풀 (dev와 교집합 없음)
TEST_SUR = list("남배설추도변마길형봉")
TEST_GIV = ["도경", "라엘", "우빈", "세아", "재윤", "린", "해든",
            "봄", "온유", "지음", "새봄", "한결"]
TEST_GU = ["늘품구", "사부작구", "도담결구", "빛솔구", "물꼬구", "바오밥구",
           "너나들이구", "아스라구", "윤우구", "다온구"]
TEST_RO = ["보라매길", "단비로", "한올로", "미쁨로", "그린비로", "여름내로",
           "아스로", "결로", "도래솔로", "봄빛로"]

# 유니크 성명 풀 (성×이름 전조합). 순차 유니크라 서로 다른 인덱스=서로 다른 성명.
DEV_FULL = [s + g for s in DEV_SUR for g in DEV_GIV]     # 400
TEST_FULL = [s + g for s in TEST_SUR for g in TEST_GIV]  # 120  (dev와 성 disjoint)


def pick(pool, i):
    return pool[i % len(pool)]


def name(full, i):
    # 17은 400·120과 서로소 → 성씨까지 고르게 분산. 오프셋(40·100·200·300)은 역할 구분.
    return full[(i * 17) % len(full)]


# ── 스펙 빌더 ─────────────────────────────────────────────────────
def clean_spec(cid, ctype, i, full, gu, ro, style):
    landlord = name(full, i)
    if ctype == "전세":
        deposit = (2 + i % 4) * 100_000_000
        rent = None
        end_years = 2
    elif ctype == "보증부월세":
        deposit = (3 + i % 5) * 10_000_000
        rent = 400_000 + (i % 4) * 100_000
        end_years = 2
    else:  # 일반월세
        deposit = (5 + i % 4) * 2_000_000
        rent = 350_000 + (i % 5) * 50_000
        end_years = 1
    contract_pay = deposit // 10
    start_m = 8 + i % 4
    return {
        "case_id": cid, "contract_type": ctype, "style": style,
        "landlord": landlord, "tenant": name(full, i + 40), "agent": None,
        "gu": pick(gu, i), "ro": pick(ro, i), "num": 10 + i, "dong": 100 + (i % 9) * 10 + 1,
        "ho": 100 * (1 + i % 15) + 1, "area": round(40 + (i % 12) * 3.7, 2),
        "deposit": deposit, "monthly_rent": rent, "contract_payment": contract_pay,
        "balance_payment": deposit - contract_pay, "account_holder": landlord,
        "start": f"2026-{start_m:02d}-05", "end": f"{2026 + end_years}-{start_m:02d}-04",
        "move_in": f"2026-{start_m:02d}-05",
        "owner": landlord, "issue_date": f"2026-{start_m:02d}-01",
        "reg_gu": None, "reg_ho": None,  # None → 계약서와 동일(R02 일치)
        "mortgage": False, "seizure": False, "trust": False,
        "return_cond": "명확", "repair": "명확", "rights_change": True,
        "unreadable": None,  # OCR 변형: 'owner'|'reg_addr'|'issue_date'
    }


def build_dev():
    """CASE-006~030 (25건). 규칙별 해당≥10·비해당≥10 커버리지 설계."""
    R01F = {0, 1, 2, 3, 4, 5, 6, 7, 8}
    R02F = {4, 5, 6, 7, 8, 9, 10, 11, 12}
    R06F = {10, 11, 12, 13, 14, 15, 16, 17, 18}
    R03F = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9}
    R04F = {9, 10, 11, 12, 13, 14, 15, 16, 17}
    R05F = {16, 17, 18, 19, 20, 21, 22, 23, 24}
    R08F = {0, 3, 6, 9, 12, 15, 18, 21, 24}
    R09F = {1, 4, 7, 10, 13, 16, 19, 22, 2}
    R10F = {2, 5, 8, 11, 14, 17, 20, 23, 0}
    AGENT = {10, 13, 16}
    OCR = {20: "owner", 21: "reg_addr", 22: "issue_date"}

    specs = []
    for i in range(25):
        cid = f"CASE-{i + 6:03d}"
        ctype = ["전세", "보증부월세", "일반월세"][i % 3]
        s = clean_spec(cid, ctype, i, DEV_FULL, DEV_GU, DEV_RO, style=i % 2)
        if i in R01F:
            s["owner"] = name(DEV_FULL, i + 100)   # 소유자 ≠ 임대인
        if i in R02F:
            s["reg_ho"] = s["ho"] + 100            # 등기 호수 다름
        if i in R06F:
            if i in AGENT:
                s["agent"] = name(DEV_FULL, i + 200)
                s["account_holder"] = s["agent"]   # 계좌=대리인
            else:
                s["account_holder"] = name(DEV_FULL, i + 300)  # 제3자 계좌
        s["mortgage"] = i in R03F
        s["seizure"] = i in R04F
        s["trust"] = i in R05F
        if i in R08F:
            s["return_cond"] = "불명확"
        if i in R09F:
            s["repair"] = "불명확"
        if i in R10F:
            s["rights_change"] = False
        if i in OCR:
            s["unreadable"] = OCR[i]
        specs.append(s)
    return specs


def build_test():
    """TEST-001~010. 전용 엔티티·전용 템플릿(style 2/3). 커버리지 쿼터 없음(held-out)."""
    plan = [  # (ctype, 발동규칙 세팅)
        ("전세", dict(owner_diff=True, mortgage=True)),
        ("보증부월세", dict()),
        ("일반월세", dict(reg_ho_diff=True, seizure=True)),
        ("전세", dict(trust=True, account_diff=True, agent=True)),
        ("전세", dict(return_cond="불명확", repair="불명확", rights_change=False)),
        ("보증부월세", dict(mortgage=True, return_cond="불명확")),
        ("일반월세", dict(owner_diff=True)),
        ("전세", dict(seizure=True, rights_change=False)),
        ("보증부월세", dict(account_diff=True)),
        ("전세", dict(mortgage=True, trust=True)),
    ]
    specs = []
    for i, (ctype, opt) in enumerate(plan):
        cid = f"TEST-{i + 1:03d}"
        s = clean_spec(cid, ctype, i, TEST_FULL, TEST_GU, TEST_RO, style=2 + i % 2)
        if opt.get("owner_diff"):
            s["owner"] = name(TEST_FULL, i + 100)
        if opt.get("reg_ho_diff"):
            s["reg_ho"] = s["ho"] + 100
        if opt.get("agent"):
            s["agent"] = name(TEST_FULL, i + 200)
        if opt.get("account_diff"):
            s["account_holder"] = s["agent"] or name(TEST_FULL, i + 300)
        s["mortgage"] = opt.get("mortgage", False)
        s["seizure"] = opt.get("seizure", False)
        s["trust"] = opt.get("trust", False)
        s["return_cond"] = opt.get("return_cond", "명확")
        s["repair"] = opt.get("repair", "명확")
        s["rights_change"] = opt.get("rights_change", True)
        specs.append(s)
    return specs


def build_extra():
    """CASE-031~034: '확인 불가' 상태 커버 보강.
    규칙 엔진이 판독불가 필드(등기 소유자·소재지)에 '확인 불가'를 ≥5회 정확히 산출하는지
    검증하기 위한 케이스. 기존 CASE-026/027과 동일 메커니즘(unreadable)이되 엔티티는 별개.
    (issue_date 판독불가는 엔진이 아직 '확인 불가'를 못 내는 알려진 결함이라 제외.)"""
    plan = ["owner", "reg_addr", "owner", "reg_addr"]
    specs = []
    for j, unread in enumerate(plan):
        i = 31 + j
        cid = f"CASE-{i:03d}"
        ctype = ["전세", "보증부월세", "일반월세"][i % 3]
        s = clean_spec(cid, ctype, i, DEV_FULL, DEV_GU, DEV_RO, style=i % 2)
        s["unreadable"] = unread
        specs.append(s)
    return specs


# ── 도출: 규칙 판정 ───────────────────────────────────────────────
def derive_rules(s):
    unread = s["unreadable"]
    reg_addr_match = s["reg_ho"] is None  # None이면 계약서와 동일

    def rule(rid, status, urg, note=None):
        r = {"rule_id": rid, "status": status, "urgency": urg}
        if note:
            r["note"] = note
        return r

    rules = []
    # R01 임대인=소유자
    if unread == "owner":
        rules.append(rule("R01", "확인 불가", "분석 불가", "등기 소유자 성명 판독 불가"))
    elif s["owner"] != s["landlord"]:
        rules.append(rule("R01", "불일치", "즉시 확인", f"계약서 임대인 {s['landlord']} ≠ 등기 소유자 {s['owner']}"))
    else:
        rules.append(rule("R01", "일치", None))
    # R02 주소 일치
    if unread == "reg_addr":
        rules.append(rule("R02", "확인 불가", "분석 불가", "등기 소재지 판독 불가"))
    elif not reg_addr_match:
        rules.append(rule("R02", "불일치", "계약 전 확인", "계약서 호수 ≠ 등기 호수"))
    else:
        rules.append(rule("R02", "일치", None))
    # R03 근저당
    rules.append(rule("R03", "확인 필요", "계약 전 확인", "을구 근저당권 기재") if s["mortgage"]
                 else rule("R03", "적용 제외", None))
    # R04 압류·가압류
    rules.append(rule("R04", "확인 필요", "즉시 확인", "갑구 가압류 기재") if s["seizure"]
                 else rule("R04", "적용 제외", None))
    # R05 신탁
    rules.append(rule("R05", "확인 필요", "즉시 확인", "갑구 신탁등기 기재") if s["trust"]
                 else rule("R05", "적용 제외", None))
    # R06 계좌 명의
    if s["account_holder"] != s["landlord"]:
        rules.append(rule("R06", "불일치", "즉시 확인", f"계좌 명의 {s['account_holder']} ≠ 임대인 {s['landlord']}"))
    else:
        rules.append(rule("R06", "일치", None))
    # R07 발급일 최신성
    if unread == "issue_date":
        rules.append(rule("R07", "확인 불가", "분석 불가", "등기 발급일 판독 불가"))
    else:
        rules.append(rule("R07", "확인 필요", "계약 전 확인", f"발급일 {s['issue_date']}, 최신성 사용자 확인"))
    # R08 보증금 반환
    rules.append(rule("R08", "불명확", "계약 전 확인", "반환 시점·조건 미특정") if s["return_cond"] == "불명확"
                 else rule("R08", "명확", None))
    # R09 수리 책임
    rules.append(rule("R09", "불명확", "참고", "수리 주체·범위 미특정") if s["repair"] == "불명확"
                 else rule("R09", "명확", None))
    # R10 권리변동 특약
    rules.append(rule("R10", "미기재", "계약 전 확인", "권리변동 제한 특약 없음") if not s["rights_change"]
                 else rule("R10", "명확", None))
    return {"case_id": s["case_id"], "contract_type": s["contract_type"], "gold_rules": rules}


def derive_extraction(s):
    unread = s["unreadable"]
    caddr = f"서울특별시 {s['gu']} {s['ro']} {s['num']}, {s['dong']}동 {s['ho']}호"
    reg_ho = s["ho"] if s["reg_ho"] is None else s["reg_ho"]
    raddr = f"서울특별시 {s['gu']} {s['ro']} {s['num']}, {s['dong']}동 {reg_ho}호"
    return {
        "case_id": s["case_id"], "contract_file": f"contract_{s['case_id']}.txt",
        "registry_file": f"registry_{s['case_id']}.txt",
        "gold_extraction": {
            "contract": {
                "contract_type": s["contract_type"], "landlord_name": s["landlord"],
                "tenant_name": s["tenant"], "agent_name": s["agent"], "property_address": caddr,
                "deposit": s["deposit"], "monthly_rent": s["monthly_rent"],
                "contract_payment": s["contract_payment"], "balance_payment": s["balance_payment"],
                "account_holder": s["account_holder"], "start_date": s["start"],
                "end_date": s["end"], "move_in_date": s["move_in"],
                "deposit_return_condition": s["return_cond"], "repair_responsibility": s["repair"],
                "rights_change_clause_present": s["rights_change"],
            },
            "registry": {
                "owner_names": None if unread == "owner" else [s["owner"]],
                "is_joint_ownership": False,
                "property_address": None if unread == "reg_addr" else raddr,
                "issue_date": None if unread == "issue_date" else s["issue_date"],
                "mortgage_present": s["mortgage"], "seizure_present": False,
                "provisional_seizure_present": s["seizure"], "trust_present": s["trust"],
            },
        },
    }


def derive_rag(s):
    fired = [r["rule_id"] for r in derive_rules(s)["gold_rules"] if r["status"] in FIRED]
    return {"case_id": s["case_id"],
            "expected_evidence": [{"rule_id": rid, "expected_source_ids": EVID[rid]} for rid in fired]}


# ── 렌더: 계약서·등기부 (style별 표면형 분리) ──────────────────────
def won(v):
    return "-" if v is None else f"₩{v:,}"


def render_contract(s):
    caddr = f"서울특별시 {s['gu']} {s['ro']} {s['num']}, {s['dong']}동 {s['ho']}호"
    header = f"[합성·비식별 샘플 — 실제 개인정보 아님 / case_id: {s['case_id']}]\n"
    rent_line = "" if s["monthly_rent"] is None else f"     차임(월세) {won(s['monthly_rent'])} (매월 지급)\n"
    ret = {"명확": "보증금은 임대차 종료 및 목적물 인도와 동시에 임대인이 반환한다.",
           "불명확": "보증금은 임대차 종료 후 임대인과 임차인이 추후 협의하여 반환한다.",
           "미기재": None}[s["return_cond"]]
    rep = {"명확": "주요 설비(보일러·급배수) 수리는 임대인이 부담하고, 임차인 고의·과실 파손은 임차인이 부담한다.",
           "불명확": "수리·원상복구는 임대인과 임차인이 상호 협의하여 처리한다.",
           "미기재": None}[s["repair"]]
    rights = "임대인은 임차인의 대항력 확보 전까지 위 부동산에 추가 담보권을 설정하지 않는다." if s["rights_change"] else None
    specials = [x for x in (ret, rep, rights) if x]
    agent_line = f"   대리인: {s['agent']} (임대인 위임)\n" if s["agent"] else ""

    if s["style"] == 0:  # dev A
        body = (f"주택임대차계약서 ({s['contract_type']})\n\n"
                f"임대인과 임차인은 아래 부동산에 관하여 다음과 같이 임대차계약을 체결한다.\n\n"
                f"1. 부동산의 표시\n   소재지: {caddr}\n   용도: 공동주택(아파트) / 면적 {s['area']}㎡\n\n"
                f"2. 계약내용\n   제1조(보증금) 보증금 {won(s['deposit'])}\n"
                f"     계약금 {won(s['contract_payment'])} (계약 시 지급)\n"
                f"     잔금 {won(s['balance_payment'])} ({s['move_in']} 지급)\n{rent_line}"
                f"   제2조(존속기간) {s['start']} ~ {s['end']}\n   제3조(입주일) {s['move_in']}\n\n")
    else:  # dev B (섹션 순서·표기 변형)
        body = (f"■ {s['contract_type']} 임대차계약서\n\n"
                f"○ 목적물: {caddr} (아파트, {s['area']}㎡)\n"
                f"○ 임대차기간: {s['start']}부터 {s['end']}까지 / 입주 {s['move_in']}\n\n"
                f"○ 대금\n  - 보증금: {won(s['deposit'])}\n  - 계약금: {won(s['contract_payment'])}\n"
                f"  - 잔금: {won(s['balance_payment'])}\n{rent_line}\n")
    if s["style"] >= 2:  # test 전용 표면형
        lbl = "가" if s["style"] == 2 else "제1항"
        body = (f"《주택 {s['contract_type']} 임대차 계약 문서》\n\n"
                f"[{lbl}] 임대 목적물 ─ {caddr} · 전용면적 {s['area']}㎡ · 공동주택\n"
                f"[{lbl}] 임대 조건 ─ 보증금 {won(s['deposit'])} / 계약금 {won(s['contract_payment'])} / "
                f"잔금 {won(s['balance_payment'])}{'' if s['monthly_rent'] is None else ' / 월차임 ' + won(s['monthly_rent'])}\n"
                f"[{lbl}] 기간 ─ {s['start']}∼{s['end']}, 입주 {s['move_in']}\n\n")

    parties = (f"3. 특약사항\n" + "".join(f"   - {x}\n" for x in specials) +
               (f"\n4. 대금 지급 계좌\n   예금주: {s['account_holder']} / ○○은행 000-00-000000\n\n" ) +
               f"   임대인: {s['landlord']} (서명 또는 날인)\n{agent_line}"
               f"   임차인: {s['tenant']} (서명 또는 날인)\n   계약일: {s['start']}\n")
    return header + "\n" + body + parties


def render_registry(s):
    unread = s["unreadable"]
    reg_ho = s["ho"] if s["reg_ho"] is None else s["reg_ho"]
    raddr = f"서울특별시 {s['gu']} {s['ro']} {s['num']}, {s['dong']}동 {reg_ho}호"
    owner_disp = "(판독 불가)" if unread == "owner" else s["owner"]
    addr_disp = "(판독 불가)" if unread == "reg_addr" else raddr
    issue_disp = "(판독 불가)" if unread == "issue_date" else s["issue_date"]
    header = f"[합성·비식별 샘플 — 실제 등기 아님 / case_id: {s['case_id']}]\n"

    gapgu = f"【갑구】 (소유권에 관한 사항)\n   소유자: {owner_disp}  (주민등록번호 800000-0000000)\n"
    if s["seizure"]:
        gapgu += f"   가압류  청구금액 {won(80_000_000)}  ○○지방법원 촉탁\n"
    if s["trust"]:
        gapgu += "   신탁  수탁자 ○○자산신탁(주)  신탁원부 제2026-0000호\n"
    eulgu = "【을구】 (소유권 이외의 권리에 관한 사항)\n"
    eulgu += (f"   근저당권설정  채권최고액 {won(int(s['deposit'] * 0.8))}  근저당권자 ○○은행\n"
              if s["mortgage"] else "   (기재 사항 없음)\n")

    if s["style"] >= 2:  # test 전용 표면형
        return (header + f"\n등기사항전부증명서 (말소사항 포함) — 열람용\n"
                f"부동산 표시: {addr_disp}\n발급일자: {issue_disp}\n\n"
                f"◎ 소유권 [갑구]  소유자 {owner_disp}" +
                ("  / 가압류 청구금액 " + won(80_000_000) if s["seizure"] else "") +
                ("  / 신탁 수탁자 ○○자산신탁(주)" if s["trust"] else "") + "\n" +
                (f"◎ 제한물권 [을구]  근저당권 채권최고액 {won(int(s['deposit'] * 0.8))}\n"
                 if s["mortgage"] else "◎ 제한물권 [을구]  없음\n"))
    return (header + f"\n등기사항전부증명서 (건물)\n\n부동산의 표시: {addr_disp}\n"
            f"열람·발급일: {issue_disp}\n\n" + gapgu + "\n" + eulgu)


def render_building_ledger(case_id, address, owner, area, ctype):
    """일반건축물대장(을) — 계약서·등기부와 소재지·용도·소유자 교차확인용 연결 문서.
    어느 R01–R10 규칙의 입력도 아님(번들 연결 데모)."""
    return (f"[합성·비식별 샘플 — 실제 대장 아님 / case_id: {case_id}]\n\n"
            f"일반건축물대장(을)\n\n"
            f"대지위치: {address}\n"
            f"주용도: 공동주택(아파트)\n"
            f"주구조: 철근콘크리트조\n"
            f"전유부분 면적: {area}㎡\n"
            f"소유자현황\n   성명: {owner}  (주민등록번호 800000-0000000)\n"
            f"   소유권 지분: 단독소유\n")


def bl_from_spec(s):
    reg_ho = s["ho"] if s["reg_ho"] is None else s["reg_ho"]
    addr = f"서울특별시 {s['gu']} {s['ro']} {s['num']}, {s['dong']}동 {reg_ho}호"
    return render_building_ledger(s["case_id"], addr, s["owner"], s["area"], s["contract_type"])


# ── 쓰기 ──────────────────────────────────────────────────────────
def write_jsonl(path, rows):
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def write_docs(specs, cdir, rdir, bdir):
    for d in (cdir, rdir, bdir):
        os.makedirs(d, exist_ok=True)
    for s in specs:
        cid = s["case_id"]
        with open(os.path.join(cdir, f"contract_{cid}.txt"), "w", encoding="utf-8") as f:
            f.write(render_contract(s))
        with open(os.path.join(rdir, f"registry_{cid}.txt"), "w", encoding="utf-8") as f:
            f.write(render_registry(s))
        with open(os.path.join(bdir, f"building_ledger_{cid}.txt"), "w", encoding="utf-8") as f:
            f.write(bl_from_spec(s))


def backfill_pilot_ledgers():
    """파일럿 5쌍(손작성)의 건축물대장 채움. 003은 이미 존재 → 001·002·004·005만."""
    import re
    bdir = os.path.join(SAMPLE, "building-ledgers")
    for row in read_jsonl(os.path.join(SAMPLE, "expected-results", "extraction_goldset.jsonl")):
        cid = row["case_id"]
        if cid not in {f"CASE-{n:03d}" for n in range(1, 6)}:
            continue
        fname = row["contract_file"].replace("contract_", "building_ledger_")
        path = os.path.join(bdir, fname)
        if os.path.exists(path):
            continue  # 003 보존
        reg = row["gold_extraction"]["registry"]
        con = row["gold_extraction"]["contract"]
        m = re.search(r"([0-9.]+)\s*㎡", open(os.path.join(SAMPLE, "contracts", row["contract_file"]), encoding="utf-8").read())
        area = m.group(1) if m else "59.5"
        with open(path, "w", encoding="utf-8") as f:
            f.write(render_building_ledger(cid, reg["property_address"], reg["owner_names"][0], area, con["contract_type"]))


def main():
    dev, test = build_dev() + build_extra(), build_test()

    # dev goldset: 파일럿 5줄 보존 + 생성 25줄
    pilots = {f"CASE-{n:03d}" for n in range(1, 6)}
    for fname, deriver in (("extraction_goldset.jsonl", derive_extraction),
                           ("rule_goldset.jsonl", derive_rules),
                           ("rag_goldset.jsonl", derive_rag)):
        path = os.path.join(SAMPLE, "expected-results", fname)
        kept = [r for r in read_jsonl(path) if r["case_id"] in pilots]
        write_jsonl(path, kept + [deriver(s) for s in dev])

    write_docs(dev, os.path.join(SAMPLE, "contracts"), os.path.join(SAMPLE, "registry-records"),
               os.path.join(SAMPLE, "building-ledgers"))
    backfill_pilot_ledgers()

    # test: 별도 디렉터리
    write_docs(test, os.path.join(E2E, "contracts"), os.path.join(E2E, "registry-records"),
               os.path.join(E2E, "building-ledgers"))
    write_jsonl(os.path.join(E2E, "final_testset_extraction.jsonl"), [derive_extraction(s) for s in test])
    write_jsonl(os.path.join(E2E, "final_testset_rule.jsonl"), [derive_rules(s) for s in test])
    write_jsonl(os.path.join(E2E, "final_testset_rag.jsonl"), [derive_rag(s) for s in test])

    print(f"생성 완료: dev {len(dev)}건(+파일럿 5) / test {len(test)}건")


def _self_check():
    # 도출 로직 무결성: 발동 조건 ↔ 상태
    s = clean_spec("T", "전세", 0, DEV_FULL, DEV_GU, DEV_RO, 0)
    assert s["landlord"] != s["tenant"], "landlord/tenant 성명 충돌"
    r = {x["rule_id"]: x for x in derive_rules(s)["gold_rules"]}
    assert r["R01"]["status"] == "일치" and r["R03"]["status"] == "적용 제외"
    assert r["R07"]["status"] == "확인 필요"  # 등기 있으면 항상
    s2 = dict(s, owner="다른사람", mortgage=True, seizure=True, trust=True,
              account_holder="제3자", return_cond="불명확", repair="불명확",
              rights_change=False, reg_ho=999)
    r2 = {x["rule_id"]: x for x in derive_rules(s2)["gold_rules"]}
    assert r2["R01"]["status"] == "불일치" and r2["R02"]["status"] == "불일치"
    assert r2["R03"]["status"] == "확인 필요" and r2["R04"]["status"] == "확인 필요"
    assert r2["R05"]["status"] == "확인 필요" and r2["R06"]["status"] == "불일치"
    assert r2["R08"]["status"] == "불명확" and r2["R10"]["status"] == "미기재"
    # OCR 변형 → 확인 불가 + 추출 None
    s3 = dict(s, unreadable="owner")
    assert derive_rules(s3)["gold_rules"][0]["status"] == "확인 불가"
    assert derive_extraction(s3)["gold_extraction"]["registry"]["owner_names"] is None
    # rag는 발동 규칙만
    assert derive_rag(s)["expected_evidence"][0]["rule_id"] == "R07"  # clean이라도 R07은 발동
    # build_extra: 확인 불가 커버 보강 4건, 각 R01 또는 R02가 확인 불가
    extra = build_extra()
    assert len(extra) == 4 and {x["case_id"] for x in extra} == {f"CASE-{n:03d}" for n in (31, 32, 33, 34)}
    cu = sum(1 for s2 in extra for r in derive_rules(s2)["gold_rules"] if r["status"] == "확인 불가")
    assert cu == 4, f"build_extra 확인 불가 {cu} != 4"
    print("gen self-check OK: 발동조건↔상태, OCR변형, rag 도출, build_extra 확인불가 일관")


if __name__ == "__main__":
    _self_check()
    main()
