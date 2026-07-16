"""문서 업로드·이력 조회. 파일은 UPLOAD_DIR(기본 backend/uploads)에 uuid명으로 저장."""

import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.api.routes.contracts import _get_owned_contract
from app.core.db import get_db
from app.models.document import Document
from app.models.user import User
from app.schemas.document import DocumentResponse, DocType

router = APIRouter(prefix="/api/contracts/{contract_id}/documents", tags=["documents"])

ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
# ponytail: 20MB 임시 상한 — 실제 스캔본 크기 보고 조정
MAX_SIZE_BYTES = 20 * 1024 * 1024


def _upload_dir() -> Path:
    d = Path(os.environ.get("UPLOAD_DIR", "uploads"))
    d.mkdir(parents=True, exist_ok=True)
    return d


@router.post("", status_code=201, response_model=DocumentResponse)
async def upload_document(
    contract_id: int,
    file: UploadFile,
    doc_type: DocType = Form(),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Document:
    contract = _get_owned_contract(contract_id, user, db)

    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "unsupported_file_type",
                "message": "PDF 또는 이미지(jpg, png) 파일만 업로드할 수 있습니다.",
            },
        )

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(
            status_code=422,
            detail={"code": "empty_file", "message": "빈 파일은 업로드할 수 없습니다."},
        )
    if len(content) > MAX_SIZE_BYTES:
        raise HTTPException(
            status_code=422,
            detail={"code": "file_too_large", "message": "파일은 20MB 이하여야 합니다."},
        )

    stored = _upload_dir() / f"{uuid.uuid4().hex}{ext}"
    stored.write_bytes(content)

    document = Document(
        contract_id=contract.id,
        doc_type=doc_type,
        filename=file.filename or f"unnamed{ext}",
        stored_path=str(stored),
        size_bytes=len(content),
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


@router.get("", response_model=list[DocumentResponse])
def list_documents(
    contract_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Document]:
    """업로드 이력 전체 (최신순). 같은 종류 재업로드도 모두 남는다."""
    contract = _get_owned_contract(contract_id, user, db)
    return list(
        db.scalars(
            select(Document)
            .where(Document.contract_id == contract.id)
            .order_by(Document.id.desc())
        )
    )
