"""특약 카탈로그(data/rules/special_clause_catalog.json) 데이터 계약 검증.

카탈로그는 새 판정 축을 만들지 않고 기존 R/J(J09~J12, R08~R10, R18~R19)에만 연결하며,
allowed_source_sections는 공식 검증 출처만 참조한다. 표현 경계에 금지 단정어를 명시한다.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
CATALOG = ROOT / "data" / "rules" / "special_clause_catalog.json"

ALLOWED_JUDGMENT_IDS = {"J09", "J10", "J11", "J12"}
ALLOWED_RULE_IDS = {"R08", "R09", "R10", "R18", "R19"}
REQUIRED_FIELDS = {
    "catalog_id",
    "version",
    "display_name",
    "related_rule_ids",
    "related_judgment_ids",
    "include_patterns",
    "exclude_patterns",
    "allowed_source_sections",
    "explanation_boundary",
}
PROHIBITED_TERMS = {"무효", "위법", "안전", "사기"}


def _official_source_ids() -> set[str]:
    manifest = ROOT / "data" / "rag" / "metadata" / "official_sources.jsonl"
    return {
        json.loads(line)["source_id"]
        for line in manifest.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }


def _spec_ids(filename: str, id_field: str) -> set[str]:
    path = ROOT / "data" / "rules" / filename
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return {row[id_field] for row in csv.DictReader(handle)}


@pytest.fixture(scope="module")
def catalog() -> dict:
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def test_catalog_has_unique_entries(catalog):
    ids = [entry["catalog_id"] for entry in catalog["entries"]]
    assert ids, "카탈로그 항목이 비어 있습니다."
    assert len(ids) == len(set(ids)), "중복 catalog_id가 있습니다."


def test_every_entry_has_required_fields(catalog):
    for entry in catalog["entries"]:
        missing = REQUIRED_FIELDS - entry.keys()
        assert not missing, f"{entry.get('catalog_id')} 필수 필드 누락: {missing}"


def test_entries_connect_only_to_allowed_rule_and_judgment_ids(catalog):
    judgment_ids = _spec_ids("judgment_spec.csv", "judgment_id")
    rule_ids = _spec_ids("rule_spec.csv", "rule_id")
    for entry in catalog["entries"]:
        related_j = set(entry["related_judgment_ids"])
        related_r = set(entry["related_rule_ids"])
        assert related_j or related_r, f"{entry['catalog_id']}는 R/J 중 하나 이상 연결해야 합니다."
        assert related_j <= ALLOWED_JUDGMENT_IDS, f"{entry['catalog_id']} 허용 밖 judgment: {related_j - ALLOWED_JUDGMENT_IDS}"
        assert related_r <= ALLOWED_RULE_IDS, f"{entry['catalog_id']} 허용 밖 rule: {related_r - ALLOWED_RULE_IDS}"
        assert related_j <= judgment_ids, f"{entry['catalog_id']} judgment_spec에 없는 id: {related_j - judgment_ids}"
        assert related_r <= rule_ids, f"{entry['catalog_id']} rule_spec에 없는 id: {related_r - rule_ids}"


def test_entries_do_not_reference_damage_pattern_ids(catalog):
    blob = json.dumps(catalog, ensure_ascii=False)
    assert not re.search(r"\bDP\d{2}\b", blob), "카탈로그는 피해유형(DP) 축을 참조하지 않아야 합니다."


def test_allowed_source_sections_reference_official_sources(catalog):
    official = _official_source_ids()
    for entry in catalog["entries"]:
        sections = entry["allowed_source_sections"]
        assert sections, f"{entry['catalog_id']} allowed_source_sections가 비어 있습니다."
        for section in sections:
            assert section["source_id"] in official, (
                f"{entry['catalog_id']} 미등록 source_id: {section['source_id']}"
            )
            assert section["article_or_section"].strip(), f"{entry['catalog_id']} 빈 section"


def test_explanation_boundary_forbids_definitive_terms(catalog):
    for entry in catalog["entries"]:
        prohibited = set(entry["explanation_boundary"]["prohibited_terms"])
        assert PROHIBITED_TERMS <= prohibited, (
            f"{entry['catalog_id']} 금지 표현 누락: {PROHIBITED_TERMS - prohibited}"
        )


def test_patterns_are_non_empty_and_compile(catalog):
    for entry in catalog["entries"]:
        assert entry["include_patterns"], f"{entry['catalog_id']} include_patterns가 비어 있습니다."
        for pattern in entry["include_patterns"] + entry["exclude_patterns"]:
            re.compile(pattern)  # 잘못된 정규식이면 여기서 실패
