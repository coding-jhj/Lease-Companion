"""SQLAlchemy 연결 설정. DATABASE_URL은 .env에서 읽는다.

연결 확인: backend/ 에서 `python -m app.core.db`
"""

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]

engine = create_engine(DATABASE_URL)
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
