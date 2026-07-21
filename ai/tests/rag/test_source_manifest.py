from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_official_source_manifest_matches_inventory_and_local_hashes():
    inventory_path = ROOT / "data" / "rules" / "source_inventory.csv"
    manifest_path = ROOT / "data" / "rag" / "metadata" / "official_sources.jsonl"

    with inventory_path.open(encoding="utf-8-sig", newline="") as source:
        expected_ids = {
            row["source_id"]
            for row in csv.DictReader(source)
            if row["source_status"] == "official_verified"
        }
    records = [json.loads(line) for line in manifest_path.read_text(encoding="utf-8").splitlines()]

    assert {record["source_id"] for record in records} == expected_ids
    assert all(record["source_status"] == "official_verified" for record in records)
    assert all(record["source_url"].startswith("https://") for record in records)
    assert all(len(record["metadata_sha256"]) == 64 for record in records)
    local_records = {
        record["source_id"]: record
        for record in records
        if record["distribution_mode"] == "local_source"
    }
    # SRC-MOLIT-CHECKLIST: 2026-07-20 팀 예외 규정으로 로컬 원문 적재 (재배포 규칙 예외 1건)
    assert set(local_records) == {
        "SRC-HTA-LAW",
        "SRC-HTA-DECREE",
        "SRC-STD-LEASE",
        "SRC-MOLIT-CHECKLIST",
        "SRC-CONFIRM-FORM",
    }
    for record in local_records.values():
        path = ROOT / record["local_path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == record["content_sha256"]
    metadata_only = [record for record in records if record["distribution_mode"] == "metadata_only"]
    assert len(metadata_only) == 4
    assert all(record["local_path"] is None for record in metadata_only)
    assert all(record["content_sha256"] is None for record in metadata_only)
