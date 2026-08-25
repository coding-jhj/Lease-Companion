"""문서 업로드·이력 조회·증빙 보관.

파일은 UPLOAD_DIR(기본 backend/uploads)에 uuid명으로 **암호화해서** 저장한다
(기획서 8) "개인정보는 암호화해서 저장").
"""

import os
import uuid
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, HTTPException, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.api.routes.contracts import _get_owned_contract
from app.core.crypto import DocumentDecryptError, read_document_bytes, write_encrypted
from app.core.db import get_db
from app.models.document import Document
from app.models.user import User
from app.schemas.document import EVIDENCE_DOC_TYPES, DocumentResponse, DocType

router = APIRouter(prefix="/api/contracts/{contract_id}/documents", tags=["documents"])

# .txt는 비식별·합성 샘플(데모·CASE 검증)용 — 실제 계약서는 pdf·이미지
ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".txt"}
# 로컬 MVP 20MB 임시 상한 — 실제 스캔본 측정과 운영 정책 확정 후 재검토
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
                "message": "PDF·이미지(jpg, png) 또는 합성 샘플 텍스트(txt)만 업로드할 수 있습니다.",
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

    stored = write_encrypted(_upload_dir() / f"{uuid.uuid4().hex}{ext}", content)

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
    kind: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Document]:
    """업로드 이력 전체 (최신순). 같은 종류 재업로드도 모두 남는다.

    `kind=evidence`면 증빙 보관물만, `kind=analysis`면 분석 입력 문서만 돌려준다.
    """
    contract = _get_owned_contract(contract_id, user, db)
    query = select(Document).where(Document.contract_id == contract.id)
    if kind == "evidence":
        query = query.where(Document.doc_type.in_(EVIDENCE_DOC_TYPES))
    elif kind == "analysis":
        query = query.where(Document.doc_type.notin_(EVIDENCE_DOC_TYPES))
    elif kind is not None:
        raise HTTPException(
            status_code=422,
            detail={"code": "unknown_document_kind", "message": "kind는 evidence 또는 analysis만 가능합니다."},
        )
    return list(db.scalars(query.order_by(Document.id.desc())))


@router.get("/{document_id}/file")
def download_document(
    contract_id: int,
    document_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """보관한 원본 내려받기 (분쟁 상담·조정 자료로 제출할 때 사용)."""
    contract = _get_owned_contract(contract_id, user, db)
    document = db.scalar(
        select(Document).where(Document.id == document_id, Document.contract_id == contract.id)
    )
    if document is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "document_not_found", "message": "문서를 찾을 수 없습니다."},
        )
    try:
        content = read_document_bytes(document.stored_path)
    except (OSError, DocumentDecryptError) as exc:
        raise HTTPException(
            status_code=500,
            detail={"code": "document_unreadable", "message": str(exc)},
        ) from exc
    return Response(
        content=content,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition":
                f"attachment; filename*=UTF-8''{quote(document.filename)}",
        },
    )


@router.delete("/{document_id}", status_code=204)
def delete_document(
    contract_id: int,
    document_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """증빙 보관물 삭제. 분석 입력 문서는 추출 이력의 원본이라 삭제하지 않는다."""
    contract = _get_owned_contract(contract_id, user, db)
    document = db.scalar(
        select(Document).where(Document.id == document_id, Document.contract_id == contract.id)
    )
    if document is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "document_not_found", "message": "문서를 찾을 수 없습니다."},
        )
    if document.doc_type not in EVIDENCE_DOC_TYPES:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "not_evidence_document",
                "message": "분석에 사용한 문서는 삭제할 수 없습니다.",
            },
        )
    Path(document.stored_path).unlink(missing_ok=True)
    db.delete(document)
    db.commit()
    return Response(status_code=204)
