"""추출·분석 백그라운드 실행 (현재 로컬 MVP: FastAPI BackgroundTasks + 폴링).

요청 세션과 분리된 자체 DB 세션을 쓴다. 실패는 행의 status=failed + error로 남긴다.
LLM 파이프라인 장시간화·재시도가 필요해지면 별도 워커 프로세스를 검토한다.
"""

import logging
import os
from pathlib import Path

from lease_companion_ai.generation.service import GenerationService
from lease_companion_ai.pipelines.minimum_mvp import extract_documents
from lease_companion_ai.providers.openai_generation import OpenAIGenerationProvider
from lease_companion_ai.schemas.adapters import analyze_snapshot, document_from_legacy
from lease_companion_ai.schemas.unified import (
    AnalysisRunResult,
    InputSnapshot,
    validate_generation_result_for_analysis,
)

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
        if run is None:
            logger.error("추출 실행 행 없음 (extraction_run_id=%s)", extraction_run_id)
            return
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
        if run is None:
            logger.error("분석 실행 행 없음 (analysis_run_pk=%s)", analysis_run_pk)
            return
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
            return
        # 규칙 결과를 먼저 안전하게 저장한 뒤 생성 단계로 넘어간다 (2026-07-17 합의).
        run.generation_status = STATUS_RUNNING
        db.commit()
        _run_generation(db, run, analysis)
        db.commit()


def _run_generation(db, run: AnalysisRun, analysis: AnalysisRunResult) -> None:
    """생성·Guardrail 단계. 실패해도 규칙 결과(result)는 건드리지 않는다.

    provider 없음·개별 규칙 실패는 GenerationService가 template fallback으로 흡수하므로
    (fallback 여부는 각 항목 generation_method로 구분) 여기 실패는 전체 생성 실패뿐이다.
    """
    try:
        provider = OpenAIGenerationProvider() if os.getenv("OPENAI_API_KEY") else None
        generation = GenerationService(provider=provider).generate(analysis)
        # 저장 직전 canonical 연결 재검증 (analysis_run_id·rule_id·source_ids)
        validate_generation_result_for_analysis(analysis, generation)
        run.generation_result = generation.model_dump(mode="json")
        run.generation_status = STATUS_COMPLETED
        run.generation_error = None
    except Exception:
        logger.exception("생성 실행 실패 (analysis_run_id=%s)", run.analysis_run_id)
        run.generation_result = None
        run.generation_status = STATUS_FAILED
        # 내부 예외 문구는 로그에만 — 사용자 노출용 안전 문구만 저장
        run.generation_error = "안내 생성에 실패했습니다. 규칙 판정 결과는 정상입니다."
