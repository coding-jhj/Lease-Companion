"""추출·분석 백그라운드 실행 (FastAPI BackgroundTasks — 폴링 방식, 2026-07-16 팀 확정).

요청 세션과 분리된 자체 DB 세션을 쓴다. 실패는 행의 status=failed + error로 남긴다.
ponytail: 프로세스 내 실행 — LLM 파이프라인 장시간화·재시도 필요해지면 별도 워커 프로세스로.
"""

import logging
from pathlib import Path

from lease_companion_ai.pipelines.minimum_mvp import extract_documents
from lease_companion_ai.schemas.adapters import analyze_snapshot, document_from_legacy
from lease_companion_ai.schemas.unified import InputSnapshot

from app.core.db import SessionLocal
from app.models.analysis import (
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_RUNNING,
    AnalysisRun,
    ExtractionRun,
)

logger = logging.getLogger(__name__)


def run_extraction(extraction_run_id: int, contract_path: str, contract_filename: str,
                   registry_path: str, registry_filename: str) -> None:
    with SessionLocal() as db:
        run = db.get(ExtractionRun, extraction_run_id)
        run.status = STATUS_RUNNING
        db.commit()
        try:
            extracted = extract_documents(
                Path(contract_path).read_bytes(), contract_filename,
                Path(registry_path).read_bytes(), registry_filename,
            )
            failures = [
                f"{label}: {doc['error']}"
                for label, doc in extracted.items()
                if not doc.get("read_ok")
            ]
            if failures:
                run.status = STATUS_FAILED
                run.error = " / ".join(failures)
            else:
                run.contract_doc = document_from_legacy(
                    extracted["contract"], document_id=f"extraction-{run.id}-contract"
                ).model_dump(mode="json")
                run.registry_doc = document_from_legacy(
                    extracted["registry"], document_id=f"extraction-{run.id}-registry"
                ).model_dump(mode="json")
                run.status = STATUS_COMPLETED
        except Exception as exc:  # 워커 크래시 = 영원히 running — 상태로 남기는 게 우선
            logger.exception("추출 실행 실패 (extraction_run_id=%s)", extraction_run_id)
            run.status = STATUS_FAILED
            run.error = str(exc)
        db.commit()


def run_analysis(analysis_run_pk: int) -> None:
    with SessionLocal() as db:
        run = db.get(AnalysisRun, analysis_run_pk)
        run.status = STATUS_RUNNING
        db.commit()
        try:
            snapshot = InputSnapshot.model_validate(run.input_snapshot)
            analysis = analyze_snapshot(snapshot, analysis_run_id=run.analysis_run_id)
            run.result = analysis.model_dump(mode="json")
            run.status = STATUS_COMPLETED
        except Exception as exc:
            logger.exception("분석 실행 실패 (analysis_run_id=%s)", run.analysis_run_id)
            run.status = STATUS_FAILED
            run.error = str(exc)
        db.commit()
