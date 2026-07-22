"""데이터셋 정합성 검증 (프레임워크 없이 assert만).

실행: python data/check_dataset.py
검증 항목:
  1) rule_spec R01–R24 × 14열, 결과상태 어휘
  2) judgment_spec J01–J12 메타데이터·상태·구현 경로
  3) 스키마 파싱
  4) source_inventory / RAG manifest / rule_evidence_map 유효성
  5) dev R goldset 3종 정합성 + J01~J12 입력·상태 goldset 파싱
  6) 커버리지: 규칙별 해당≥10·비해당≥10 (R07은 항상 발동 → 보고만)
  7) 누수: dev∩test 문서 본문(case_id 제외) 중복 0
  8) 테스트셋(final_testset) 파싱·문서 존재·근거 유효
  9) 검증된 유사 참고 사례: DP01~DP08 coverage·중복·공식 URL·경계 설명
  10) 개인정보: 실제형 주민번호·휴대폰 패턴 0
"""
import csv
import hashlib
import json
import os
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
SAMPLE = os.path.join(BASE, "sample")
E2E = os.path.join(BASE, "evaluation", "end-to-end")

COMMON_STATUS = {"일치", "불일치", "명확", "불명확", "미기재", "상충 가능", "확인 필요", "확인 불가", "적용 제외"}
CLEAN = {"일치", "명확", "적용 제외"}                        # 비해당
FIRED = {"불일치", "확인 필요", "불명확", "미기재", "상충 가능"}  # 해당
RULE_IDS = [f"R{n:02d}" for n in range(1, 25)]
CORE_RULE_IDS = [f"R{n:02d}" for n in range(1, 11)]
JUDGMENT_IDS = [f"J{n:02d}" for n in range(1, 13)]
QUOTA_RULES = [r for r in CORE_RULE_IDS if r != "R07"]      # 기존 goldset 쿼터는 R01~R10만 유지
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
    lines = [line for line in open(path, encoding="utf-8").read().splitlines() if "case_id" not in line]
    norm = re.sub(r"\s+", " ", " ".join(lines)).strip()
    return hashlib.sha1(norm.encode("utf-8")).hexdigest()


def file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    # 1) rule_spec
    with open(os.path.join(BASE, "rules/rule_spec.csv"), encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 24, f"rule_spec 행 {len(rows)} != 24"
    assert [r["rule_id"] for r in rows] == RULE_IDS, "rule_id가 R01–R24가 아님"
    assert len(rows[0].keys()) == 14, f"rule_spec 열 {len(rows[0].keys())} != 14"
    for r in rows:
        for status in r["result_status"].split("|"):
            assert status in COMMON_STATUS, f"{r['rule_id']} 미허용 상태 {status}"

    # 2) J 판정 메타데이터
    with open(os.path.join(BASE, "rules/judgment_spec.csv"), encoding="utf-8") as f:
        judgment_rows = list(csv.DictReader(f))
    assert [row["judgment_id"] for row in judgment_rows] == JUDGMENT_IDS
    assert len(judgment_rows[0].keys()) == 15
    for row in judgment_rows:
        assert row["version"], f"{row['judgment_id']} version 누락"
        assert row["implementation"].startswith("rules/judgments.py:_j")
        for status in row["result_status"].split("|"):
            assert status in COMMON_STATUS, f"{row['judgment_id']} 미허용 상태 {status}"

    # 3) 스키마
    for name in ("legacy/contract_schema.json", "legacy/registry_schema.json"):
        with open(os.path.join(BASE, "schemas", name), encoding="utf-8") as f:
            json.load(f)

    # 4) source_inventory / evidence_map
    with open(os.path.join(BASE, "rules/source_inventory.csv"), encoding="utf-8") as f:
        source_rows = list(csv.DictReader(f))
    assert len(source_rows) == 16, f"source_inventory 행 {len(source_rows)} != 16"
    allowed_source_statuses = {"official_verified", "synthetic_reference", "unverified", "excluded"}
    for row in source_rows:
        assert row["source_status"] in allowed_source_statuses, f"미허용 source_status {row['source_status']}"
        if row["source_status"] == "official_verified":
            assert row["institution"].strip(), f"공식자료 기관 누락 {row['source_id']}"
            assert row["source_url"].startswith("https://"), f"공식자료 URL 누락 {row['source_id']}"
    sources = {row["source_id"] for row in source_rows}
    official_sources = {
        row["source_id"] for row in source_rows
        if row["source_status"] == "official_verified"
    }
    manifest_path = os.path.join(BASE, "rag", "metadata", "official_sources.jsonl")
    manifest = read_jsonl(manifest_path)
    assert {row["source_id"] for row in manifest} == official_sources, "RAG manifest 공식 출처 불일치"
    for row in manifest:
        assert row["source_status"] == "official_verified"
        assert row["source_url"].startswith("https://")
        assert row["distribution_mode"] in {"metadata_only", "local_source"}
        expected_metadata_hash = row["metadata_sha256"]
        hash_payload = {key: value for key, value in row.items() if key != "metadata_sha256"}
        encoded = json.dumps(
            hash_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        assert hashlib.sha256(encoded).hexdigest() == expected_metadata_hash
        if row["distribution_mode"] == "local_source":
            local_path = os.path.join(os.path.dirname(BASE), row["local_path"])
            assert os.path.isfile(local_path), f"RAG 로컬 원문 없음 {row['source_id']}"
            assert file_sha256(local_path) == row["content_sha256"]
        else:
            assert row["local_path"] is None and row["content_sha256"] is None
    with open(os.path.join(BASE, "rules/rule_evidence_map.csv"), encoding="utf-8") as f:
        for row in csv.DictReader(f):
            assert row["rule_id"] in RULE_IDS, f"evidence_map 미확인 규칙 {row['rule_id']}"
            assert row["source_id"] in sources, f"evidence_map 미확인 근거 {row['source_id']}"
            assert row["source_id"] in official_sources, f"evidence_map 비공식 근거 {row['source_id']}"

    # 4-1) 유사 참고 사례는 공식 근거와 분리된 표시용 로컬 corpus다.
    reference_case_path = os.path.join(
        BASE, "reference-cases", "verified_reference_cases.json"
    )
    with open(reference_case_path, encoding="utf-8") as f:
        reference_catalog = json.load(f)
    assert reference_catalog["schema_version"] == "1.0.0"
    reference_ids = []
    covered_patterns = set()
    allowed_reference_hosts = (
        "https://www.khug.or.kr/",
        "https://adrhome.reb.or.kr/",
    )
    for entry in reference_catalog["cases"]:
        assert entry["pattern_ids"]
        assert set(entry["pattern_ids"]) <= {
            f"DP{index:02d}" for index in range(1, 9)
        }
        covered_patterns.update(entry["pattern_ids"])
        reference = entry["reference_case"]
        reference_ids.append(reference["reference_case_id"])
        assert reference["title"].strip()
        assert reference["publisher"].strip()
        assert reference["summary"].strip()
        assert reference["verification_scope"].strip()
        assert reference["source_url"].startswith(allowed_reference_hosts)
    assert len(reference_ids) == len(set(reference_ids)), "유사 참고 사례 ID 중복"
    assert covered_patterns == {f"DP{index:02d}" for index in range(1, 9)}

    def assert_no_runtime_contract_ids(value):
        if isinstance(value, dict):
            forbidden_keys = {"contract_id", "analysis_run_id", "practice_session_id"}
            assert not (set(value) & forbidden_keys), "연습 fixture에 실제 runtime 식별자 포함"
            for child in value.values():
                assert_no_runtime_contract_ids(child)
        elif isinstance(value, list):
            for child in value:
                assert_no_runtime_contract_ids(child)

    # 4-2) 계약 연습 합성 fixture 구조·교차참조·결정성
    practice_root = os.path.join(SAMPLE, "practice-scenarios")
    practice_dirs = sorted(
        entry.path
        for entry in os.scandir(practice_root)
        if entry.is_dir() and entry.name.startswith("PRACTICE-")
    )
    assert practice_dirs, "계약 연습 fixture 없음"
    expected_answer_statuses = [
        "appropriate_check",
        "partial_check",
        "ambiguous_answer",
        "avoidance",
        "no_response",
        "needs_review",
    ]
    for practice_dir in practice_dirs:
        with open(os.path.join(practice_dir, "scenario.json"), encoding="utf-8") as f:
            practice_scenario = json.load(f)
        with open(os.path.join(practice_dir, "answer-key.json"), encoding="utf-8") as f:
            practice_answers = json.load(f)

        assert practice_scenario["fixture_type"] == "synthetic_practice_scenario"
        assert practice_scenario["data_classification"] == "synthetic"
        assert practice_scenario["scenario_id"] == practice_answers["scenario_id"]
        assert practice_scenario["scenario_version"] == practice_answers["scenario_version"]
        assert practice_scenario["review_status"] in {"user_review_pending", "approved"}
        assert practice_answers["review_status"] in {"user_review_pending", "approved"}

        action_ids = [row["action_id"] for row in practice_scenario["target_actions"]]
        assert action_ids == [f"PA{index:02d}" for index in range(1, len(action_ids) + 1)]
        assert [row["action_id"] for row in practice_answers["action_rubrics"]] == action_ids

        signal_ids = [
            row["signal_id"] for row in practice_scenario["hidden_confirmation_signals"]
        ]
        assert len(signal_ids) == len(set(signal_ids)), "연습 signal_id 중복"
        for action in practice_scenario["target_actions"]:
            assert set(action["linked_signal_ids"]) <= set(signal_ids)
        for signal in practice_scenario["hidden_confirmation_signals"]:
            assert set(signal["linked_rule_ids"]) <= set(RULE_IDS)
            assert set(signal["linked_judgment_ids"]) <= set(JUDGMENT_IDS)
            assert set(signal["official_source_ids"]) <= official_sources

        turn_ids = [row["turn_id"] for row in practice_scenario["dialogue_turns"]]
        assert turn_ids == [f"TURN-{index:02d}" for index in range(1, len(turn_ids) + 1)]
        answer_statuses = [row["status_id"] for row in practice_answers["answer_statuses"]]
        assert answer_statuses == expected_answer_statuses
        for turn in practice_scenario["dialogue_turns"]:
            assert turn["goal_action_id"] in action_ids
            assert list(turn["responses"]) == expected_answer_statuses
            assert turn["next_turn_id"] in set(turn_ids) | {"ACTION-SELECTION"}

        example_ids = set()
        deterministic_outputs = {}
        represented_statuses = set()
        valid_next_turn_ids = set(turn_ids) | {"ACTION-SELECTION"}
        for example in practice_answers["evaluation_examples"]:
            assert example["example_id"] not in example_ids, "연습 example_id 중복"
            example_ids.add(example["example_id"])
            assert example["turn_id"] in turn_ids
            assert example["expected_status_id"] in answer_statuses
            represented_statuses.add(example["expected_status_id"])
            assert set(example["expected_confirmed_action_ids"]) <= set(action_ids)
            assert example["expected_next_turn_id"] in valid_next_turn_ids
            input_key = json.dumps(
                [example["turn_id"], example["user_input"], example["input_context"]],
                ensure_ascii=False,
                sort_keys=True,
            )
            output_value = (
                example["expected_status_id"],
                tuple(example["expected_confirmed_action_ids"]),
                example["expected_next_turn_id"],
            )
            if input_key in deterministic_outputs:
                assert deterministic_outputs[input_key] == output_value, (
                    "동일 연습 입력의 기대 출력 충돌"
                )
            deterministic_outputs[input_key] = output_value
        assert represented_statuses == set(answer_statuses), "연습 답변 상태 예시 누락"
        assert set(practice_answers["debrief"]["official_source_ids"]) <= official_sources
        assert_no_runtime_contract_ids(practice_scenario)
        assert_no_runtime_contract_ids(practice_answers)

    # 5) dev R goldset 3종 + J 입력·상태 goldset
    er = os.path.join(SAMPLE, "expected-results")
    rule_g = read_jsonl(os.path.join(er, "rule_goldset.jsonl"))
    extr_g = read_jsonl(os.path.join(er, "extraction_goldset.jsonl"))
    rag_g = read_jsonl(os.path.join(er, "rag_goldset.jsonl"))
    ids = {c["case_id"] for c in rule_g}
    assert {c["case_id"] for c in extr_g} == ids == {c["case_id"] for c in rag_g}, "dev goldset case_id 불일치"
    assert len(ids) >= 30, f"dev 케이스 {len(ids)} < 30"
    judgment_g = read_jsonl(os.path.join(er, "judgment_goldset.jsonl"))
    assert [row["judgment_id"] for row in judgment_g] == JUDGMENT_IDS
    judgment_case_ids = []
    for row in judgment_g:
        assert row["cases"], f"{row['judgment_id']} gold case 없음"
        for case in row["cases"]:
            judgment_case_ids.append(case["case_id"])
            assert case["expected_status"] in COMMON_STATUS
            assert case["contract_fields"] is not None
            assert case["registry_fields"] is not None
    assert len(judgment_case_ids) == len(set(judgment_case_ids)), "J gold case_id 중복"

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
                    assert sid in official_sources, f"{label} {c['case_id']} rag 비공식 근거 {sid}"

    validate(rule_g, extr_g, rag_g, "dev")

    # 6) 커버리지: 규칙별 해당/비해당
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

    # 7) 누수: dev vs test 문서 본문 중복 0
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

    # 8) 테스트셋
    tids = {c["case_id"] for c in trule}
    assert {c["case_id"] for c in textr} == tids == {c["case_id"] for c in trag}, "test goldset case_id 불일치"
    assert tids and all(t.startswith("TEST") for t in tids), "test case_id 접두 오류"
    assert len(tids) >= 10, f"test 케이스 {len(tids)} < 10"
    validate(trule, textr, trag, "test")

    # 9) 개인정보 스캔 (dev + test 문서 + RAG 로컬 원문)
    real_rrn = re.compile(r"\d{6}-[1-4]\d{6}")
    phone = re.compile(r"01[016789]-\d{3,4}-\d{4}")
    for root in (SAMPLE, E2E, os.path.join(BASE, "rag", "sources")):
        for dirpath, _, files in os.walk(root):
            for fn in files:
                if not fn.endswith((".txt", ".json", ".jsonl")):
                    continue
                text = open(os.path.join(dirpath, fn), encoding="utf-8").read()
                assert not real_rrn.search(text), f"{fn} 실제형 주민번호 패턴"
                assert not phone.search(text), f"{fn} 휴대폰 패턴"

    print(
        f"\nOK: dev {len(ids)}쌍 + test {len(tids)}쌍, 규칙 24(기존 gold 쿼터 10), "
        f"J gold {len(judgment_case_ids)}건, 연습 fixture {len(practice_dirs)}건, 누수 0, 개인정보 0"
    )


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
