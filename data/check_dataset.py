"""파일럿 데이터셋 정합성 검증 (프레임워크 없이 assert만).

실행: python data/check_dataset.py
plan(glimmering-weaving-koala)의 '검증 방법' 5종을 확인한다.
"""
import csv
import json
import os
import re

BASE = os.path.dirname(os.path.abspath(__file__))

COMMON_STATUS = {"일치", "불일치", "명확", "불명확", "미기재", "상충 가능", "확인 필요", "확인 불가", "적용 제외"}
RULE_IDS = [f"R{n:02d}" for n in range(1, 11)]
CASE_IDS = {f"CASE-{n:03d}" for n in range(1, 6)}


def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def main():
    # 1) rule_spec: R01–R10 × 14열(13필드 + judgment_id)
    with open(os.path.join(BASE, "rules/rule_spec.csv"), encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 10, f"rule_spec 행 {len(rows)} != 10"
    assert [r["rule_id"] for r in rows] == RULE_IDS, "rule_id가 R01–R10이 아님"
    assert len(rows[0].keys()) == 14, f"rule_spec 열 {len(rows[0].keys())} != 14"
    for r in rows:
        for status in r["result_status"].split("|"):
            assert status in COMMON_STATUS, f"{r['rule_id']} 미허용 상태 {status}"

    # 2) 스키마 파싱
    for name in ("contract_schema.json", "registry_schema.json"):
        with open(os.path.join(BASE, "schemas", name), encoding="utf-8") as f:
            json.load(f)

    # 3) source_inventory → id 집합
    with open(os.path.join(BASE, "rules/source_inventory.csv"), encoding="utf-8") as f:
        sources = {row["source_id"] for row in csv.DictReader(f)}

    # 4) rule_evidence_map: rule_id·source_id 유효
    with open(os.path.join(BASE, "rules/rule_evidence_map.csv"), encoding="utf-8") as f:
        for row in csv.DictReader(f):
            assert row["rule_id"] in RULE_IDS, f"evidence_map 미확인 규칙 {row['rule_id']}"
            assert row["source_id"] in sources, f"evidence_map 미확인 근거 {row['source_id']}"

    # 5) goldset 3종: case 일치·상태 어휘·파일 존재·근거 유효
    rule_g = read_jsonl(os.path.join(BASE, "sample/expected-results/rule_goldset.jsonl"))
    extr_g = read_jsonl(os.path.join(BASE, "sample/expected-results/extraction_goldset.jsonl"))
    rag_g = read_jsonl(os.path.join(BASE, "sample/expected-results/rag_goldset.jsonl"))
    for g in (rule_g, extr_g, rag_g):
        assert {c["case_id"] for c in g} == CASE_IDS, "goldset case_id 집합 불일치"

    for c in rule_g:
        for gr in c["gold_rules"]:
            assert gr["rule_id"] in RULE_IDS
            assert gr["status"] in COMMON_STATUS, f"{c['case_id']} {gr['rule_id']} 상태 {gr['status']}"

    for c in extr_g:
        for key in ("contract_file", "registry_file"):
            sub = "contracts" if key == "contract_file" else "registry-records"
            path = os.path.join(BASE, "sample", sub, c[key])
            assert os.path.exists(path), f"문서 없음 {path}"

    for c in rag_g:
        for ev in c["expected_evidence"]:
            for sid in ev["expected_source_ids"]:
                assert sid in sources, f"{c['case_id']} rag 근거 미확인 {sid}"

    # 6) 개인정보 스캔: 실제형 주민번호·휴대폰 패턴 0 (합성은 마스킹 6자리-0000000)
    real_rrn = re.compile(r"\d{6}-[1-4]\d{6}")
    phone = re.compile(r"01[016789]-\d{3,4}-\d{4}")
    doc_dir = os.path.join(BASE, "sample")
    for root, _, files in os.walk(doc_dir):
        for fn in files:
            if not fn.endswith(".txt"):
                continue
            text = open(os.path.join(root, fn), encoding="utf-8").read()
            assert not real_rrn.search(text), f"{fn} 실제형 주민번호 패턴"
            assert not phone.search(text), f"{fn} 휴대폰 패턴"

    print("OK: rule_spec 10규칙, 스키마 2, goldset 3×5케이스, 근거 매핑, 개인정보 스캔 통과")


if __name__ == "__main__":
    main()
