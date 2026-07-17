"""FastAPI 진입점.

실행: backend/ 에서 `uvicorn app.main:app --reload`
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import analyses, auth, checklists, contracts, documents, extractions, feedback
from app.core.db import Base, engine
from app.core.errors import register_error_handlers


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Alembic 도입 전 로컬 MVP 임시 처리. 기존 테이블 변경은 적용하지 못한다.
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="슬기로운 계약생활 API", version="0.0.0", lifespan=lifespan)
register_error_handlers(app)

app.include_router(auth.router)
app.include_router(contracts.router)
app.include_router(documents.router)
app.include_router(extractions.router)
app.include_router(analyses.router)
app.include_router(checklists.router)
app.include_router(feedback.router)


@app.get("/health")
def health() -> dict[str, str]:
    """서비스 기동 확인용 헬스체크."""
    return {"status": "ok"}


# TODO: results 통합 리포트 라우터 — A의 canonical GenerationResult 확정 후 모양 결정
#       (현재는 analysis-runs result JSON + checklist-items 조합으로 커버)
