from __future__ import annotations

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_rule_map_and_rag_goldsets_use_only_official_verified_sources():
    with (ROOT / "data/rules/source_inventory.csv").open(encoding="utf-8", newline="") as handle:
        inventory = list(csv.DictReader(handle))
    official = {
        row["source_id"]
        for row in inventory
        if row["source_status"] == "official_verified"
    }

    with (ROOT / "data/rules/rule_evidence_map.csv").open(encoding="utf-8", newline="") as handle:
        mapped = {row["source_id"] for row in csv.DictReader(handle)}
    assert mapped <= official

    paths = (
        ROOT / "data/sample/expected-results/rag_goldset.jsonl",
        ROOT / "data/evaluation/end-to-end/final_testset_rag.jsonl",
    )
    for path in paths:
        with path.open(encoding="utf-8") as handle:
            rows = [json.loads(line) for line in handle if line.strip()]
        expected = {
            source_id
            for row in rows
            for evidence in row["expected_evidence"]
            for source_id in evidence["expected_source_ids"]
        }
        assert expected <= official
