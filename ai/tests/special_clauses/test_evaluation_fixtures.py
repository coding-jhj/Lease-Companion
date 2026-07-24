"""잠긴 특약 오프라인 평가셋의 구조·분리·근거 범위를 검증한다."""

from __future__ import annotations

import hashlib
import json
from itertools import product
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EVAL_DIR = ROOT / "data" / "evaluation" / "special-clauses"
CATALOG_PATH = ROOT / "data" / "rules" / "special_clause_catalog.json"
OFFICIAL_SOURCES = ROOT / "data" / "rag" / "metadata" / "official_sources.jsonl"
LOCK_PATH = EVAL_DIR / "locked_test_hashes.json"

CATEGORIES = {
    "positive_paraphrase",
    "normal_negative",
    "negation",
    "conditional_exception",
    "compound",
}
LOCKED_TEST_FILES = {
    "catalog_test.jsonl",
    "retrieval_test.jsonl",
    "generation_cases.jsonl",
}
BASE_PROHIBITED_TERMS = {"무효", "위법", "안전", "사기"}
# 잠긴 평가셋이 실제로 다루는 카탈로그 항목. J13 연결 5종은 실제 계약서 문구 샘플 확보 후
# 패턴을 넓히면서 평가셋에 넣기로 미뤘다.
# → docs/decisions/2026-07-23-j13-tenant-protection-restriction.md "패턴 정확도의 한계"
EVALUATED_CATALOG_IDS = {
    "SC-DEFERRED-REFUND",
    "SC-REPAIR-SCOPE",
    "SC-RESTORATION-SCOPE",
    "SC-RIGHTS-CHANGE",
    "SC-MANAGEMENT-FEE",
    "SC-MAIN-SPECIAL-CONFLICT",
}


def _jsonl(filename: str) -> list[dict]:
    path = EVAL_DIR / filename
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _catalog() -> dict:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def _catalog_ids() -> set[str]:
    return {entry["catalog_id"] for entry in _catalog()["entries"]}


def _normalized(text: str) -> str:
    return " ".join(text.split()).casefold()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_catalog_test_covers_every_type_and_category_once():
    assert EVALUATED_CATALOG_IDS <= _catalog_ids(), "평가 대상 항목이 카탈로그에서 사라졌습니다."
    cases = _jsonl("catalog_test.jsonl")
    expected_pairs = set(product(EVALUATED_CATALOG_IDS, CATEGORIES))
    actual_pairs = {(case["target_catalog_id"], case["category"]) for case in cases}

    assert len(cases) == len(expected_pairs) == 30
    assert actual_pairs == expected_pairs
    assert len({case["case_id"] for case in cases}) == len(cases)
    assert len({_normalized(case["text"]) for case in cases}) == len(cases)


def test_catalog_test_labels_follow_category_contract():
    catalog_ids = _catalog_ids()
    for case in _jsonl("catalog_test.jsonl"):
        target = case["target_catalog_id"]
        expected = case["expected_catalog_ids"]
        assert set(expected) <= catalog_ids
        assert len(expected) == len(set(expected))
        if case["category"] == "positive_paraphrase":
            assert expected == [target]
        elif case["category"] == "compound":
            assert target in expected
            assert len(expected) >= 2
        else:
            assert target not in expected


def test_dev_and_test_texts_do_not_overlap():
    for dev_name, test_name in (
        ("catalog_dev.jsonl", "catalog_test.jsonl"),
        ("retrieval_dev.jsonl", "retrieval_test.jsonl"),
    ):
        dev_texts = {_normalized(case["text"]) for case in _jsonl(dev_name)}
        test_texts = {_normalized(case["text"]) for case in _jsonl(test_name)}
        assert dev_texts.isdisjoint(test_texts), f"{dev_name}과 {test_name}에 같은 문장이 있습니다."


def test_retrieval_test_covers_six_types_and_no_evidence():
    cases = _jsonl("retrieval_test.jsonl")
    targets = {case["target_catalog_id"] for case in cases}
    assert targets == EVALUATED_CATALOG_IDS | {None}
    assert len({case["case_id"] for case in cases}) == len(cases)
    assert any(not case["expect_evidence"] for case in cases)


def test_retrieval_ground_truth_uses_allowed_official_sections():
    catalog = {entry["catalog_id"]: entry for entry in _catalog()["entries"]}
    official_ids = {row["source_id"] for row in _jsonl_from_path(OFFICIAL_SOURCES)}

    for case in _jsonl("retrieval_test.jsonl"):
        source_ids = case["expected_source_ids"]
        sections = case["expected_sections"]
        assert len(source_ids) == len(sections)
        assert set(source_ids) <= official_ids
        if not case["expect_evidence"]:
            assert case["target_catalog_id"] is None
            assert source_ids == [] and sections == []
            continue

        target = case["target_catalog_id"]
        allowed = {
            (section["source_id"], section["article_or_section"])
            for section in catalog[target]["allowed_source_sections"]
        }
        assert set(zip(source_ids, sections, strict=True)) <= allowed


def _jsonl_from_path(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_generation_cases_cover_six_types_and_no_evidence():
    cases = _jsonl("generation_cases.jsonl")
    assert {case["target_catalog_id"] for case in cases} == EVALUATED_CATALOG_IDS | {None}
    assert len({case["case_id"] for case in cases}) == len(cases)

    for case in cases:
        assert case["allowed_core_meaning"].strip()
        assert BASE_PROHIBITED_TERMS <= set(case["prohibited_terms"])
        if case["target_catalog_id"] is None:
            assert case["expect_evidence"] is False


def test_locked_test_files_match_recorded_sha256():
    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    assert lock["algorithm"] == "sha256"
    assert lock["review_status"] == "draft_pending_human_review"
    assert set(lock["files"]) == LOCKED_TEST_FILES
    for filename, expected_hash in lock["files"].items():
        assert _sha256(EVAL_DIR / filename) == expected_hash, f"잠긴 평가 파일 변경: {filename}"
