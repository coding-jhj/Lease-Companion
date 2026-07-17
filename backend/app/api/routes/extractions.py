"""추출 실행(비동기)·확인·수정 API — 통합 스키마 경계.

원본 보존 원칙: ExtractionRun의 추출 결과는 절대 갱신하지 않고,
CorrectionRecord 이력을 순서대로 재적용(재생)해 현재 상태를 계산한다.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from lease_companion_ai.schemas.adapters import (
    apply_correction_request,
    build_snapshot,
    confirm_document,
)
from lease_companion_ai.schemas.unified import CorrectionRequest, DocumentExtraction, DocumentType

from app.api.dependencies.auth import get_current_user
from app.api.routes.contracts import _contract_context, _get_owned_contract, _registry_file
from app.core.db import get_db
from app.models.analysis import STATUS_COMPLETED, CorrectionRecord, ExtractionRun, InputSnapshotRecord
from app.models.contract import ContractProject
from app.models.document import Document
from app.models.user import User
from app.schemas.analysis import ExtractionState, SnapshotResponse
from app.workers.analysis import run_extraction

router = APIRouter(prefix="/api/contracts/{contract_id}", tags=["extractions"])


def _latest_document(db: Session, contract_id: int, doc_type: str) -> Document | None:
    return db.scalar(
        select(Document)
        .where(Document.contract_id == contract_id, Document.doc_type == doc_type)
        .order_by(Document.id.desc())
        .limit(1)
    )


def _latest_extraction(db: Session, contract_id: int) -> ExtractionRun | None:
    return db.scalar(
        select(ExtractionRun)
        .where(ExtractionRun.contract_id == contract_id)
        .order_by(ExtractionRun.id.desc())
        .limit(1)
    )


def _replayed_documents(
    db: Session, run: ExtractionRun
) -> dict[DocumentType, DocumentExtraction]:
    """원본 추출 결과 + 수정 이력 재생 = 현재 상태. 원본 행은 건드리지 않는다."""
    documents = {
        DocumentType.CONTRACT: DocumentExtraction.model_validate(run.contract_doc),
        DocumentType.REGISTRY: DocumentExtraction.model_validate(run.registry_doc),
    }
    corrections = db.scalars(
        select(CorrectionRecord)
        .where(CorrectionRecord.extraction_run_id == run.id)
        .order_by(CorrectionRecord.id)
    )
    for record in corrections:
        documents = apply_correction_request(
            documents, CorrectionRequest.model_validate(record.payload)
        )
    return documents


def _completed_extraction(db: Session, contract: ContractProject) -> ExtractionRun:
    run = _latest_extraction(db, contract.id)
    if run is None or run.status != STATUS_COMPLETED:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "extraction_not_ready",
                "message": "완료된 추출 결과가 없습니다. 추출을 먼저 실행·완료하세요.",
            },
        )
    return run


@router.post("/extractions", status_code=202, response_model=ExtractionState)
def start_extraction(
    contract_id: int,
    background: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExtractionRun:
    """업로드된 계약서(+등기 문서 또는 모의 등기 연결)로 추출을 시작한다.

    즉시 202를 반환하고, 완료 여부는 GET …/extractions/latest 폴링으로 확인한다.
    """
    contract = _get_owned_contract(contract_id, user, db)

    contract_doc = _latest_document(db, contract.id, "계약서")
    if contract_doc is None:
        raise HTTPException(
            status_code=422,
            detail={"code": "missing_contract_document", "message": "업로드된 계약서가 없습니다."},
        )

    registry_doc = _latest_document(db, contract.id, "등기사항증명서")
    if registry_doc is not None:
        registry_path, registry_name = registry_doc.stored_path, registry_doc.filename
    else:
        fixture = _registry_file(contract.registry_case_id) if contract.registry_case_id else None
        if fixture is None:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "missing_registry_source",
                    "message": "등기사항증명서 업로드 또는 모의 등기 연결(registry-link)이 필요합니다.",
                },
            )
        registry_path, registry_name = str(fixture), fixture.name

    run = ExtractionRun(contract_id=contract.id)
    db.add(run)
    db.commit()
    db.refresh(run)
    background.add_task(
        run_extraction, run.id, contract_doc.stored_path, contract_doc.filename,
        registry_path, registry_name,
    )
    return run


@router.get("/extractions/latest", response_model=ExtractionState)
def get_latest_extraction(
    contract_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExtractionState:
    """최신 추출 상태 폴링 + (완료 시) 수정 이력이 반영된 현재 추출값."""
    contract = _get_owned_contract(contract_id, user, db)
    run = _latest_extraction(db, contract.id)
    if run is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": "추출 실행 이력이 없습니다."},
        )
    state = ExtractionState.model_validate(run, from_attributes=True)
    if run.status == STATUS_COMPLETED:
        documents = _replayed_documents(db, run)
        state.contract_doc = documents[DocumentType.CONTRACT].model_dump(mode="json")
        state.registry_doc = documents[DocumentType.REGISTRY].model_dump(mode="json")
    return state


@router.post("/corrections", status_code=201, response_model=ExtractionState)
def apply_corrections(
    contract_id: int,
    body: dict,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExtractionState:
    """통합 CorrectionRequest를 검증·적용하고 이력으로 보존한다. 원본 추출값은 유지된다."""
    contract = _get_owned_contract(contract_id, user, db)
    run = _completed_extraction(db, contract)
    try:
        request = CorrectionRequest.model_validate(body)
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_correction_request", "message": "수정 요청이 통합 스키마와 맞지 않습니다."},
        ) from exc
    if request.contract_id != contract.id:
        raise HTTPException(
            status_code=422,
            detail={"code": "contract_id_mismatch", "message": "수정 요청의 contract_id가 경로의 계약 건과 다릅니다."},
        )
    try:
        documents = apply_correction_request(_replayed_documents(db, run), request)
    except KeyError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "unknown_correction_field", "message": str(exc.args[0])},
        ) from exc

    db.add(
        CorrectionRecord(
            contract_id=contract.id,
            extraction_run_id=run.id,
            payload=request.model_dump(mode="json"),
        )
    )
    db.commit()
    state = ExtractionState.model_validate(run, from_attributes=True)
    state.contract_doc = documents[DocumentType.CONTRACT].model_dump(mode="json")
    state.registry_doc = documents[DocumentType.REGISTRY].model_dump(mode="json")
    return state


@router.post("/extractions/confirm", status_code=201, response_model=SnapshotResponse)
def confirm_extraction(
    contract_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SnapshotResponse:
    """사용자의 추출값 확인 완료 — 서버가 불변 InputSnapshot을 생성·보존한다.

    이후 분석 실행(POST …/analysis-runs)은 이 스냅샷을 사용한다.
    """
    contract = _get_owned_contract(contract_id, user, db)
    context = _contract_context(contract)  # 상황 미입력 시 422 missing_contract_context
    run = _completed_extraction(db, contract)
    documents = _replayed_documents(db, run)
    snapshot = build_snapshot(
        input_snapshot_id=f"snap-{uuid.uuid4().hex}",
        contract_id=contract.id,
        contract_context=context,
        case_id=contract.registry_case_id,
        contract_doc=confirm_document(documents[DocumentType.CONTRACT]),
        registry_doc=confirm_document(documents[DocumentType.REGISTRY]),
        confirmed_at=datetime.now(timezone.utc),
    )
    record = InputSnapshotRecord(
        contract_id=contract.id,
        input_snapshot_id=snapshot.input_snapshot_id,
        payload=snapshot.model_dump(mode="json"),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return SnapshotResponse(
        input_snapshot_id=record.input_snapshot_id,
        created_at=record.created_at,
        snapshot=record.payload,
    )
