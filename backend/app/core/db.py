"""SQLAlchemy 연결 설정. DATABASE_URL은 .env에서 읽는다.

연결 확인: backend/ 에서 `python -m app.core.db`
"""

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]

# sqlite는 테스트 전용 (TestClient가 다른 스레드에서 접근하므로 check_same_thread 해제)
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

# SQL_ECHO=true면 실행되는 모든 SQL을 콘솔에 실시간 출력한다 (디버깅용, 기본 꺼짐).
_echo = os.getenv("SQL_ECHO", "").lower() == "true"

# pool_pre_ping: 사용 전 커넥션을 가볍게 검사해 idle 중 끊긴(=stale) 커넥션을 자동 교체한다.
# 없으면 DB 재시작·idle 타임아웃 후 첫 요청이 500으로 실패하고 재시도해야 성공한다.
engine = create_engine(
    DATABASE_URL, connect_args=_connect_args, echo=_echo, pool_pre_ping=True
)
SessionLocal = sessionmaker(bind=engine, autoflush=False)


class Base(DeclarativeBase):
    """모든 영속 모델의 공통 베이스 (app/models/ 에서 상속)."""


def get_db():
    """FastAPI 의존성: 요청 단위 DB 세션."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


if __name__ == "__main__":
    with engine.connect() as conn:
        assert conn.execute(text("SELECT 1")).scalar() == 1
    print(f"DB 연결 OK: {engine.url.render_as_string(hide_password=True)}")
