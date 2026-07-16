"""환경변수로 명시적으로 요청한 경우에만 로컬 개발 계정을 생성한다."""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pydantic import ValidationError
from sqlalchemy import select

from app.core import security
from app.core.db import Base, SessionLocal, engine
from app.models.user import User
from app.schemas.auth import SignupRequest


def load_seed_request() -> SignupRequest | None:
    values = {
        "username": os.getenv("DEV_SEED_USERNAME"),
        "email": os.getenv("DEV_SEED_EMAIL"),
        "password": os.getenv("DEV_SEED_PASSWORD"),
    }
    if not all(values.values()):
        print("시드 생성을 건너뜁니다. DEV_SEED_USERNAME, DEV_SEED_EMAIL, DEV_SEED_PASSWORD를 모두 설정하세요.")
        return None
    try:
        return SignupRequest.model_validate(values)
    except ValidationError as exc:
        print("시드 계정 값이 가입 규칙을 충족하지 않습니다.")
        raise SystemExit(2) from exc


def main() -> None:
    request = load_seed_request()
    if request is None:
        return
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.username == request.username)):
            print(f"시드 계정이 이미 존재합니다: {request.username}")
            return
        db.add(
            User(
                username=request.username,
                email=request.email,
                password_hash=security.hash_password(request.password),
            )
        )
        db.commit()
        print(f"시드 계정을 생성했습니다: {request.username}")


if __name__ == "__main__":
    main()
