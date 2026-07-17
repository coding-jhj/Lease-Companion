"""분석 실행(비동기)·결과 저장·재조회 API — 통합 스키마 경계.

POST는 즉시 202를 반환하고, 결과는 GET 폴링으로 확인한다(2026-07-16 팀 확정).
입력 스냅샷은 추출 확인 API(POST …/extractions/confirm)가 만든 서버 측 사본을 사용한다.
"""

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.api.routes.contracts import _get_owned_contract
from app.core.db import get_db
from app.models.analysis import AnalysisRun, InputSnapshotRecord
from app.models.user import User
from app.schemas.analysis import AnalysisRunDetail, AnalysisRunSummary
from app.workers.analysis import run_analysis

router = APIRouter(prefix="/api/contracts/{contract_id}/analysis-runs", tags=["analyses"])


@router.post("", status_code=202, response_model=AnalysisRunDetail)
def start_analysis(
    contract_id: int,
    background: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AnalysisRun:
    """최신 확인 완료 스냅샷으로 분석을 시작한다. 재분석마다 새 행이 쌓인다(이력)."""
    contract = _get_owned_contract(contract_id, user, db)
    snapshot = db.scalar(
        select(InputSnapshotRecord)
        .where(InputSnapshotRecord.contract_id == contract.id)
        .order_by(InputSnapshotRecord.id.desc())
        .limit(1)
    )
    if snapshot is None:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "no_confirmed_snapshot",
                "message": "확인 완료된 추출값이 없습니다. 추출값 확인(…/extractions/confirm)을 먼저 완료하세요.",
            },
        )
    run = AnalysisRun(
        contract_id=contract.id,
        analysis_run_id=uuid.uuid4().hex,
        input_snapshot_id=snapshot.input_snapshot_id,
        input_snapshot=snapshot.payload,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    background.add_task(run_analysis, run.id)
    return run


@router.get("", response_model=list[AnalysisRunSummary])
def list_analysis_runs(
    contract_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AnalysisRun]:
    """재분석 이력 (최신순)."""
    contract = _get_owned_contract(contract_id, user, db)
    return list(
        db.scalars(
            select(AnalysisRun)
            .where(AnalysisRun.contract_id == contract.id)
            .order_by(AnalysisRun.id.desc())
        )
    )


@router.get("/{analysis_run_id}", response_model=AnalysisRunDetail)
def get_analysis_run(
    contract_id: int,
    analysis_run_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AnalysisRun:
    """분석 상태·결과 폴링. completed면 result에 통합 AnalysisRunResult JSON이 담긴다."""
    contract = _get_owned_contract(contract_id, user, db)
    run = db.scalar(
        select(AnalysisRun).where(
            AnalysisRun.contract_id == contract.id,
            AnalysisRun.analysis_run_id == analysis_run_id,
        )
    )
    if run is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": "해당 분석 실행을 찾을 수 없습니다."},
        )
    return run
