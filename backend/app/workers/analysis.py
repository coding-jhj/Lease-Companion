"""추출·분석 백그라운드 실행 (현재 로컬 MVP: FastAPI BackgroundTasks + 폴링).

요청 세션과 분리된 자체 DB 세션을 쓴다. 실패는 행의 status=failed + error로 남긴다.
LLM 파이프라인 장시간화·재시도가 필요해지면 별도 워커 프로세스를 검토한다.
"""

import logging
import os
from pathlib import Path

from sqlalchemy import select

from lease_companion_ai.classification.service import ClassificationService
from lease_companion_ai.schemas.unified import ClassificationMethod
from lease_companion_ai.generation.service import GenerationService
from lease_companion_ai.pipelines.classified_analysis import (
    analyze_special_clause_evidence,
)
from lease_companion_ai.pipelines.minimum_mvp import extract_documents
from lease_companion_ai.providers.gemini_classification import GeminiClassificationProvider
from lease_companion_ai.providers.gemini_generation import GeminiGenerationProvider
from lease_companion_ai.schemas.adapters import document_from_legacy
from lease_companion_ai.schemas.unified import (
    AnalysisRunResult,
    ContractContext,
    GenerationMethod,
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
                   registry_path: str | None, registry_filename: str | None) -> None:
    with SessionLocal() as db:
        run = db.get(ExtractionRun, extraction_run_id)
        if run is None:
            logger.error("추출 실행 행 없음 (extraction_run_id=%s)", extraction_run_id)
            return
        run.status = STATUS_RUNNING
        db.commit()
        logger.info("[1/4] 문서 추출 시작 (extraction_run_id=%s)", extraction_run_id)
        try:
            extracted = extract_documents(
                Path(contract_path).read_bytes(), contract_filename,
                Path(registry_path).read_bytes() if registry_path else None, registry_filename,
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
        logger.info(
            "[1/4] 문서 추출 종료 (extraction_run_id=%s status=%s %s)",
            extraction_run_id,
            run.status,
            _extraction_summary(run),
        )
        if run.status == STATUS_FAILED:
            logger.warning(
                "[1/4] 추출 실패 사유 (extraction_run_id=%s): %s",
                extraction_run_id,
                run.error,
            )


def _reason_histogram(items) -> str:
    """폴백 사유 분포. 사유는 결과 JSON에만 있고 로그엔 없어서 원인 추적이 막혔었다."""
    counts: dict[str, int] = {}
    for item in items:
        key = item.fallback_reason or "unspecified"
        counts[key] = counts.get(key, 0) + 1
    return ",".join(f"{key}:{count}" for key, count in sorted(counts.items())) or "없음"


def _status_histogram(results) -> str:
    """판정 상태 분포를 `불일치:2,미기재:5` 형태로 요약한다."""
    counts: dict[str, int] = {}
    for result in results:
        key = getattr(result.status, "value", str(result.status))
        counts[key] = counts.get(key, 0) + 1
    return ",".join(f"{key}:{count}" for key, count in sorted(counts.items())) or "없음"


def _extraction_summary(run: ExtractionRun) -> str:
    """추출 결과를 값 노출 없이 요약한다. 원문·개인정보는 남기지 않는다."""
    parts = []
    for label, doc in (("계약서", run.contract_doc), ("등기", run.registry_doc)):
        if not doc:
            parts.append(f"{label}=없음")
            continue
        fields = doc.get("fields") or {}
        # 값 자체는 절대 로그에 남기지 않는다. 판독 성공/실패 개수만 센다.
        read = sum(
            1
            for field in fields.values()
            if isinstance(field, dict) and field.get("extracted_value") is not None
        )
        parts.append(f"{label}=판독{read}/{len(fields)}")
    return " ".join(parts)


def run_analysis(analysis_run_pk: int) -> None:
    with SessionLocal() as db:
        run = db.get(AnalysisRun, analysis_run_pk)
        if run is None:
            logger.error("분석 실행 행 없음 (analysis_run_pk=%s)", analysis_run_pk)
            return
        run.status = STATUS_RUNNING
        db.commit()
        logger.info("[2/4] 구조화·규칙 판정 시작 (analysis_run_id=%s)", run.analysis_run_id)
        try:
            snapshot = InputSnapshot.model_validate(run.input_snapshot)
            classification_service = ClassificationService(
                provider=_classification_provider()
            )
            classification, analysis = analyze_special_clause_evidence(
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
            # 구조화가 safe_fallback으로 떨어지면 후보가 0이 되어 특약 근거·안내가
            # 조용히 비는데, 지금까지는 그 사실이 어디에도 남지 않았다.
            if classification.classification_method != ClassificationMethod.PROVIDER:
                logger.warning(
                    "[2/4] 조항 구조화 fallback (analysis_run_id=%s method=%s 후보=%d) "
                    "— 특약 근거·안내가 비게 됩니다",
                    run.analysis_run_id,
                    classification.classification_method.value,
                    len(classification.candidates),
                )
            # 데모 해설용 단계 요약 — 판정 id·건수만. 문서 내용·개인정보는 남기지 않는다.
            logger.info(
                "[3/4] 규칙 판정 완료 (analysis_run_id=%s R=%d J=%d 특약카드=%d "
                "즉시확인=%d 상태=%s 근거있음=%d/%d)",
                run.analysis_run_id,
                len(analysis.results),
                len(analysis.judgments),
                len(analysis.special_clause_reviews),
                sum(1 for r in analysis.results if r.urgency == "즉시 확인"),
                _status_histogram(analysis.results),
                sum(1 for r in analysis.results if r.evidence_sources),
                len(analysis.results),
            )
            if not any(r.evidence_sources for r in analysis.results):
                logger.warning(
                    "[3/4] 공식 근거 0건 (analysis_run_id=%s) — RAG 검색 실패 또는 "
                    "임베딩 한도 소진. 생성 단계가 전량 템플릿 폴백이 됩니다",
                    run.analysis_run_id,
                )
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
        provider = GeminiGenerationProvider() if (
            os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        ) else None
        generation = GenerationService(provider=provider).generate(
            analysis, contract_context
        )
        # 저장 직전 canonical 연결 재검증 (analysis_run_id·rule_id·source_ids)
        validate_generation_result_for_analysis(analysis, generation)
        run.generation_result = generation.model_dump(mode="json")
        run.generation_status = STATUS_COMPLETED
        run.generation_error = None
        fallbacks = [
            item
            for item in generation.items
            if item.generation_method is not GenerationMethod.PROVIDER
        ]
        logger.info(
            "[4/4] 안내 생성 완료 (analysis_run_id=%s provider=%s 규칙안내=%d 특약안내=%d "
            "템플릿폴백=%d 사유=%s)",
            run.analysis_run_id,
            "gemini" if provider else "none",
            len(generation.items),
            len(generation.special_clause_items),
            len(fallbacks),
            _reason_histogram(fallbacks),
        )
        if fallbacks and len(fallbacks) == len(generation.items):
            logger.warning(
                "[4/4] 규칙 안내 전량 템플릿 폴백 (analysis_run_id=%s 사유=%s) "
                "— LLM 생성 결과가 하나도 반영되지 않았습니다",
                run.analysis_run_id,
                _reason_histogram(fallbacks),
            )
    except Exception:
        logger.exception("생성 실행 실패 (analysis_run_id=%s)", run.analysis_run_id)
        # provider 경로가 통째로 실패해도(설정·네트워크·SDK 예외 등) 규칙 recommended_actions 기반
        # 템플릿 폴백으로 최소 체크리스트는 보장한다 — 8번 행동 화면이 비지 않도록.
        try:
            generation = GenerationService(provider=None).generate(analysis, contract_context)
            validate_generation_result_for_analysis(analysis, generation)
            run.generation_result = generation.model_dump(mode="json")
            run.generation_status = STATUS_COMPLETED
            run.generation_error = None
        except Exception:
            logger.exception("템플릿 폴백 생성도 실패 (analysis_run_id=%s)", run.analysis_run_id)
            run.generation_result = None
            run.generation_status = STATUS_FAILED
            # 내부 예외 문구는 로그에만 — 사용자 노출용 안전 문구만 저장
            run.generation_error = "안내 생성에 실패했습니다. 규칙 판정 결과는 정상입니다."
