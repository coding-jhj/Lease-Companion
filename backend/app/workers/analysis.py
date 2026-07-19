"""추출·분석 백그라운드 실행 (현재 로컬 MVP: FastAPI BackgroundTasks + 폴링).

요청 세션과 분리된 자체 DB 세션을 쓴다. 실패는 행의 status=failed + error로 남긴다.
LLM 파이프라인 장시간화·재시도가 필요해지면 별도 워커 프로세스를 검토한다.
"""

import logging
import os
from pathlib import Path

from sqlalchemy import select

from lease_companion_ai.classification.service import ClassificationService
from lease_companion_ai.generation.service import GenerationService
from lease_companion_ai.pipelines.classified_analysis import analyze_with_classification
from lease_companion_ai.pipelines.minimum_mvp import extract_documents
from lease_companion_ai.providers.gemini_classification import GeminiClassificationProvider
from lease_companion_ai.providers.openai_generation import OpenAIGenerationProvider
from lease_companion_ai.schemas.adapters import document_from_legacy
from lease_companion_ai.schemas.unified import (
    AnalysisRunResult,
    ContractContext,
    InputSnapshot,
    validate_generation_result_for_analysis,
)

from app.core.db import SessionLocal
from app.models.analysis import (
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_RUNNING,
    AnalysisRun,
    ExtractionRun,
)

logger = logging.getLogger(__name__)

# 서버 재시작으로 중단된 실행에 남기는 사용자 노출용 문구
_INTERRUPTED = "서버 재시작으로 실행이 중단되었습니다. 다시 실행해 주세요."


def fail_stale_runs() -> None:
    """기동 시 pending/running으로 남은 실행을 failed로 정리한다.

    BackgroundTasks는 프로세스 내 실행이라 서버가 내려가면 진행 중이던 행이
    영원히 pending/running으로 남아 클라이언트가 무한 폴링하게 된다.
    """
    with SessionLocal() as db:
        stale_states = (STATUS_PENDING, STATUS_RUNNING)
        for extraction_run in db.scalars(
            select(ExtractionRun).where(ExtractionRun.status.in_(stale_states))
        ):
            extraction_run.status = STATUS_FAILED
            extraction_run.error = _INTERRUPTED
        for analysis_run in db.scalars(
            select(AnalysisRun).where(AnalysisRun.status.in_(stale_states))
        ):
            analysis_run.status = STATUS_FAILED
            analysis_run.error = _INTERRUPTED
        for generation_run in db.scalars(
            select(AnalysisRun).where(AnalysisRun.generation_status.in_(stale_states))
        ):
            generation_run.generation_status = STATUS_FAILED
            generation_run.generation_error = _INTERRUPTED
        db.commit()


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
            classification_service = ClassificationService(
                provider=_classification_provider()
            )
            classification, analysis = analyze_with_classification(
                snapshot,
                analysis_run_id=run.analysis_run_id,
                classification_service=classification_service,
            )
            # classification 실패는 safe_fallback(후보 없음)으로 흡수되어 규칙이 명세대로
            # 확인 필요/확인 불가를 낸다. provenance(fallback 사유)는 결과 JSON에 담긴다.
            # classification_result는 내부 저장 전용 — API 응답에 노출하지 않는다(BC §B-4).
            run.classification_result = classification.model_dump(mode="json")
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
        _run_generation(db, run, analysis, snapshot.contract_context)
        db.commit()


def _classification_provider():
    """분류 provider 키가 있으면 Gemini provider, 없으면 None.

    None이면 ClassificationService가 safe_fallback(후보 없음)을 반환하므로 키 없이도
    분석은 완료된다. 생성 provider와 동일한 키-게이팅 패턴.
    """
    if os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"):
        return GeminiClassificationProvider()
    return None


def _run_generation(
    db,
    run: AnalysisRun,
    analysis: AnalysisRunResult,
    contract_context: ContractContext,
) -> None:
    """생성·Guardrail 단계. 실패해도 규칙 결과(result)는 건드리지 않는다.

    provider 없음·개별 규칙 실패는 GenerationService가 template fallback으로 흡수하므로
    (fallback 여부는 각 항목 generation_method로 구분) 여기 실패는 전체 생성 실패뿐이다.
    """
    try:
        provider = OpenAIGenerationProvider() if os.getenv("OPENAI_API_KEY") else None
        generation = GenerationService(provider=provider).generate(
            analysis, contract_context
        )
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
