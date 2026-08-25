"""업로드 문서 저장 암호화(at rest).

기획서 "개인정보는 암호화해서 저장" 근거. 업로드 원본은 계약서·등기·증빙 모두
개인정보를 포함하므로 디스크에 평문으로 두지 않는다.

키는 `DOCUMENT_ENCRYPTION_KEY`(Fernet urlsafe base64 32바이트)를 쓰고, 없으면
로컬 MVP 편의를 위해 `JWT_SECRET`에서 결정론적으로 파생한다.
"""

from __future__ import annotations

import base64
import hashlib
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

# 암호화된 파일에 붙이는 접미사. 저장 경로만 보고 복호화 여부를 판단한다
# (합성 fixture·데모 텍스트는 평문 그대로 읽어야 하므로 컬럼 대신 접미사로 구분).
ENCRYPTED_SUFFIX = ".enc"


class DocumentDecryptError(RuntimeError):
    """키 불일치·파일 손상으로 복호화 불가."""


def _fernet() -> Fernet:
    key = os.environ.get("DOCUMENT_ENCRYPTION_KEY")
    if key:
        return Fernet(key.encode("utf-8"))
    # ponytail: JWT_SECRET 파생 키. 운영 전환 시 KMS·별도 키 회전으로 교체한다.
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        raise RuntimeError(
            "문서 암호화 키가 없습니다. DOCUMENT_ENCRYPTION_KEY 또는 JWT_SECRET을 설정하세요."
        )
    derived = hashlib.sha256(f"document-at-rest:{secret}".encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(derived))


def write_encrypted(path: Path, content: bytes) -> Path:
    """`path`에 암호문을 쓰고 실제 저장 경로(`…{ENCRYPTED_SUFFIX}`)를 돌려준다."""
    target = path.with_name(path.name + ENCRYPTED_SUFFIX)
    target.write_bytes(_fernet().encrypt(content))
    return target


def read_document_bytes(path: str | Path) -> bytes:
    """업로드 문서 읽기. 암호화 접미사가 없으면 합성 fixture이므로 그대로 읽는다."""
    file = Path(path)
    raw = file.read_bytes()
    if file.suffix != ENCRYPTED_SUFFIX:
        return raw
    try:
        return _fernet().decrypt(raw)
    except InvalidToken as exc:
        raise DocumentDecryptError(
            f"저장된 문서를 복호화할 수 없습니다: {file.name}"
        ) from exc
