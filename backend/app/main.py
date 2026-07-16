"""FastAPI 진입점.

실행: backend/ 에서 `uvicorn app.main:app --reload`
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import auth, contracts
from app.core.db import Base, engine
from app.core.errors import register_error_handlers


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ponytail: Alembic 도입 전 임시 — 테이블이 없으면 만든다 (기존 테이블 변경은 못 함)
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="슬기로운 계약생활 API", version="0.0.0", lifespan=lifespan)
register_error_handlers(app)

app.include_router(auth.router)
app.include_router(contracts.router)


@app.get("/health")
def health() -> dict[str, str]:
    """서비스 기동 확인용 헬스체크."""
    return {"status": "ok"}


# TODO: 남은 라우터 등록 (documents·extractions·analyses·results·checklists·feedback)
