"""공식 검증 RAG 출처의 결정적 메타데이터 manifest를 생성한다."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INVENTORY = ROOT / "data" / "rules" / "source_inventory.csv"
DEFAULT_SOURCE_DIR = ROOT / "data" / "rag" / "sources"
DEFAULT_OUTPUT = ROOT / "data" / "rag" / "metadata" / "official_sources.jsonl"

REQUIRED_FIELDS = (
    "source_id",
    "title",
    "institution",
    "document_type",
    "article_or_section",
    "source_url",
    "retrieved_at",
    "usage_terms",
    "verification_note",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _metadata_sha256(record: dict[str, Any]) -> str:
    payload = json.dumps(
        record,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def build_manifest(
    inventory_path: Path = DEFAULT_INVENTORY,
    source_dir: Path = DEFAULT_SOURCE_DIR,
) -> list[dict[str, Any]]:
    with inventory_path.open(encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))

    records: list[dict[str, Any]] = []
    for row in rows:
        if row["source_status"] != "official_verified":
            continue
        missing = [field for field in REQUIRED_FIELDS if not row.get(field, "").strip()]
        if missing:
            raise ValueError(f"{row.get('source_id', '<unknown>')} 필수 메타데이터 누락: {missing}")
        if not row["source_url"].startswith("https://"):
            raise ValueError(f"{row['source_id']} 공식 URL은 https여야 합니다.")

        local_candidate = source_dir / row["local_file"]
        redistribution_allowed = row["usage_terms"].startswith("재배포 허용:")
        has_local_source = local_candidate.is_file() and redistribution_allowed
        record: dict[str, Any] = {
            "source_id": row["source_id"],
            "source_status": "official_verified",
            "title": row["title"],
            "institution": row["institution"],
            "document_type": row["document_type"],
            "effective_or_published_date": row["effective_or_published_date"] or None,
            "article_or_section": row["article_or_section"],
            "source_url": row["source_url"],
            "retrieved_at": row["retrieved_at"],
            "usage_terms": row["usage_terms"],
            "verification_note": row["verification_note"],
            "distribution_mode": "local_source" if has_local_source else "metadata_only",
            "local_path": local_candidate.relative_to(ROOT).as_posix() if has_local_source else None,
            "content_sha256": _sha256(local_candidate) if has_local_source else None,
        }
        record["metadata_sha256"] = _metadata_sha256(record)
        records.append(record)

    source_ids = [record["source_id"] for record in records]
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("공식 출처 manifest에 중복 source_id가 있습니다.")
    return sorted(records, key=lambda record: record["source_id"])


def write_manifest(records: list[dict[str, Any]], output_path: Path = DEFAULT_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    content = "".join(
        json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records
    )
    output_path.write_text(content, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    records = build_manifest(args.inventory, args.source_dir)
    write_manifest(records, args.output)
    print(f"official_sources={len(records)} output={args.output}")


if __name__ == "__main__":
    main()
