"""데이터셋 정합성 검증 (프레임워크 없이 assert만).

실행: python data/check_dataset.py
검증 항목:
  1) rule_spec R01–R10 × 14열, 결과상태 어휘
  2) 스키마 파싱
  3) source_inventory / rule_evidence_map 유효성
  4) dev goldset 3종 case_id 집합 일치·상태 어휘·문서 존재·근거 유효
  5) 커버리지: 규칙별 해당≥10·비해당≥10 (R07은 항상 발동 → 보고만)
  6) 누수: dev∩test 문서 본문(case_id 제외) 중복 0
  7) 테스트셋(final_testset) 파싱·문서 존재·근거 유효
  8) 개인정보: 실제형 주민번호·휴대폰 패턴 0
"""
import csv
import hashlib
import json
import os
import re

BASE = os.path.dirname(os.path.abspath(__file__))
SAMPLE = os.path.join(BASE, "sample")
E2E = os.path.join(BASE, "evaluation", "end-to-end")

COMMON_STATUS = {"일치", "불일치", "명확", "불명확", "미기재", "상충 가능", "확인 필요", "확인 불가", "적용 제외"}
CLEAN = {"일치", "명확", "적용 제외"}                        # 비해당
FIRED = {"불일치", "확인 필요", "불명확", "미기재", "상충 가능"}  # 해당
RULE_IDS = [f"R{n:02d}" for n in range(1, 11)]
QUOTA_RULES = [r for r in RULE_IDS if r != "R07"]           # R07은 항상 발동, 쿼터 제외
QUOTA = 10


def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def doc_dir(case_id, kind):
    root = E2E if case_id.startswith("TEST") else SAMPLE
    sub = {"contract": "contracts", "registry": "registry-records", "building": "building-ledgers"}[kind]
    return os.path.join(root, sub)


def body_hash(path):
    """case_id 헤더 줄을 제외한 본문 정규화 해시 (표면형 비교용)."""
    lines = [l for l in open(path, encoding="utf-8").read().splitlines() if "case_id" not in l]
    norm = re.sub(r"\s+", " ", " ".join(lines)).strip()
    return hashlib.sha1(norm.encode("utf-8")).hexdigest()


def main():
    # 1) rule_spec
    with open(os.path.join(BASE, "rules/rule_spec.csv"), encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 10, f"rule_spec 행 {len(rows)} != 10"
    assert [r["rule_id"] for r in rows] == RULE_IDS, "rule_id가 R01–R10이 아님"
    assert len(rows[0].keys()) == 14, f"rule_spec 열 {len(rows[0].keys())} != 14"
    for r in rows:
        for status in r["result_status"].split("|"):
            assert status in COMMON_STATUS, f"{r['rule_id']} 미허용 상태 {status}"

    # 2) 스키마
    for name in ("contract_schema.json", "registry_schema.json"):
        with open(os.path.join(BASE, "schemas", name), encoding="utf-8") as f:
            json.load(f)

    # 3) source_inventory / evidence_map
    with open(os.path.join(BASE, "rules/source_inventory.csv"), encoding="utf-8") as f:
        sources = {row["source_id"] for row in csv.DictReader(f)}
    with open(os.path.join(BASE, "rules/rule_evidence_map.csv"), encoding="utf-8") as f:
        for row in csv.DictReader(f):
            assert row["rule_id"] in RULE_IDS, f"evidence_map 미확인 규칙 {row['rule_id']}"
            assert row["source_id"] in sources, f"evidence_map 미확인 근거 {row['source_id']}"

    # 4) dev goldset 3종
    er = os.path.join(SAMPLE, "expected-results")
    rule_g = read_jsonl(os.path.join(er, "rule_goldset.jsonl"))
    extr_g = read_jsonl(os.path.join(er, "extraction_goldset.jsonl"))
    rag_g = read_jsonl(os.path.join(er, "rag_goldset.jsonl"))
    ids = {c["case_id"] for c in rule_g}
    assert {c["case_id"] for c in extr_g} == ids == {c["case_id"] for c in rag_g}, "dev goldset case_id 불일치"
    assert len(ids) >= 30, f"dev 케이스 {len(ids)} < 30"

    def validate(rule_rows, extr_rows, rag_rows, label):
        for c in rule_rows:
            for gr in c["gold_rules"]:
                assert gr["rule_id"] in RULE_IDS
                assert gr["status"] in COMMON_STATUS, f"{label} {c['case_id']} {gr['rule_id']} 상태 {gr['status']}"
        for c in extr_rows:
            for kind, key in (("contract", "contract_file"), ("registry", "registry_file")):
                p = os.path.join(doc_dir(c["case_id"], kind), c[key])
                assert os.path.exists(p), f"{label} 문서 없음 {p}"
            # ③ 건축물대장 연결: 케이스마다 대응 파일 존재 (contract_* 규칙 파생)
            bl = c["contract_file"].replace("contract_", "building_ledger_")
            blp = os.path.join(doc_dir(c["case_id"], "building"), bl)
            assert os.path.exists(blp), f"{label} 건축물대장 없음 {blp}"
        for c in rag_rows:
            for ev in c["expected_evidence"]:
                for sid in ev["expected_source_ids"]:
                    assert sid in sources, f"{label} {c['case_id']} rag 근거 미확인 {sid}"

    validate(rule_g, extr_g, rag_g, "dev")

    # 5) 커버리지: 규칙별 해당/비해당
    tally = {rid: {"해당": 0, "비해당": 0, "불가": 0} for rid in RULE_IDS}
    for c in rule_g:
        for gr in c["gold_rules"]:
            b = "해당" if gr["status"] in FIRED else "비해당" if gr["status"] in CLEAN else "불가"
            tally[gr["rule_id"]][b] += 1
    print("커버리지(dev):")
    for rid in RULE_IDS:
        t = tally[rid]
        note = "  [R07 항상 발동—쿼터 제외]" if rid == "R07" else ""
        print(f"  {rid}  해당 {t['해당']:>2}  비해당 {t['비해당']:>2}  확인불가 {t['불가']:>2}{note}")
    for rid in QUOTA_RULES:
        assert tally[rid]["해당"] >= QUOTA, f"{rid} 해당 {tally[rid]['해당']} < {QUOTA}"
        assert tally[rid]["비해당"] >= QUOTA, f"{rid} 비해당 {tally[rid]['비해당']} < {QUOTA}"

    # 6) 누수: dev vs test 문서 본문 중복 0
    trule = read_jsonl(os.path.join(E2E, "final_testset_rule.jsonl"))
    textr = read_jsonl(os.path.join(E2E, "final_testset_extraction.jsonl"))
    trag = read_jsonl(os.path.join(E2E, "final_testset_rag.jsonl"))
    dev_hashes, test_hashes = set(), set()
    for c in extr_g:
        for kind, key in (("contract", "contract_file"), ("registry", "registry_file")):
            dev_hashes.add(body_hash(os.path.join(doc_dir(c["case_id"], kind), c[key])))
    for c in textr:
        for kind, key in (("contract", "contract_file"), ("registry", "registry_file")):
            test_hashes.add(body_hash(os.path.join(doc_dir(c["case_id"], kind), c[key])))
    leak = dev_hashes & test_hashes
    assert not leak, f"누수: dev/test 동일 본문 {len(leak)}건"

    # 7) 테스트셋
    tids = {c["case_id"] for c in trule}
    assert {c["case_id"] for c in textr} == tids == {c["case_id"] for c in trag}, "test goldset case_id 불일치"
    assert tids and all(t.startswith("TEST") for t in tids), "test case_id 접두 오류"
    assert len(tids) >= 10, f"test 케이스 {len(tids)} < 10"
    validate(trule, textr, trag, "test")

    # 8) 개인정보 스캔 (dev + test 문서)
    real_rrn = re.compile(r"\d{6}-[1-4]\d{6}")
    phone = re.compile(r"01[016789]-\d{3,4}-\d{4}")
    for root in (SAMPLE, E2E):
        for dirpath, _, files in os.walk(root):
            for fn in files:
                if not fn.endswith(".txt"):
                    continue
                text = open(os.path.join(dirpath, fn), encoding="utf-8").read()
                assert not real_rrn.search(text), f"{fn} 실제형 주민번호 패턴"
                assert not phone.search(text), f"{fn} 휴대폰 패턴"

    print(f"\nOK: dev {len(ids)}쌍 + test {len(tids)}쌍, 규칙 10, 커버리지 쿼터 충족, 누수 0, 개인정보 0")


if __name__ == "__main__":
    main()
