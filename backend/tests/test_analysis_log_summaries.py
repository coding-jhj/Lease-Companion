"""로그 요약 헬퍼 검증 — 값 노출 금지와 분포 집계가 깨지면 진단이 다시 막힌다."""

from types import SimpleNamespace

from app.workers.analysis import (
    _extraction_summary,
    _reason_histogram,
    _status_histogram,
)


def test_status_histogram_counts_by_status_value():
    results = [
        SimpleNamespace(status=SimpleNamespace(value="불일치")),
        SimpleNamespace(status=SimpleNamespace(value="미기재")),
        SimpleNamespace(status=SimpleNamespace(value="미기재")),
    ]
    assert _status_histogram(results) == "미기재:2,불일치:1"
    assert _status_histogram([]) == "없음"


def test_reason_histogram_labels_missing_reason():
    items = [
        SimpleNamespace(fallback_reason="missing_evidence"),
        SimpleNamespace(fallback_reason="missing_evidence"),
        SimpleNamespace(fallback_reason=None),
    ]
    assert _reason_histogram(items) == "missing_evidence:2,unspecified:1"


def test_extraction_summary_counts_reads_without_leaking_values():
    run = SimpleNamespace(
        contract_doc={
            "fields": {
                "landlord_name": {"extracted_value": "홍길동"},
                "deposit": {"extracted_value": None},
            }
        },
        registry_doc=None,
    )
    summary = _extraction_summary(run)
    assert summary == "계약서=판독1/2 등기=없음"
    assert "홍길동" not in summary
