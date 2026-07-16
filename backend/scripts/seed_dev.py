"""로컬 개발용 시드 계정 생성. 실행: backend/ 에서 `python scripts/seed_dev.py`

가입 API의 비밀번호 규칙을 우회해 DB에 직접 넣는다 — 로컬 개발 DB 전용.
메인(공유) 서버 전환 후에는 실행하지 않는다.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.core import security
from app.core.db import Base, SessionLocal, engine
from app.models.user import User

USERNAME = "admin"
EMAIL = "admin@test.com"
PASSWORD = "1234"


def main() -> None:
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.username == USERNAME)):
            print(f"이미 존재함: {USERNAME} (비밀번호 {PASSWORD})")
            return
        db.add(
            User(
                username=USERNAME,
                email=EMAIL,
                password_hash=security.hash_password(PASSWORD),
            )
        )
        db.commit()
        print(f"시드 계정 생성: {USERNAME} / {PASSWORD}")


if __name__ == "__main__":
    main()
