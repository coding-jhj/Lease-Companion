"""FastAPI 진입점.

실행: backend/ 에서 `uvicorn app.main:app --reload`
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import analyses, auth, checklists, contracts, documents, extractions, feedback
from app.core.db import Base, engine
from app.core.errors import register_error_handlers
from app.workers.analysis import fail_stale_runs


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 스키마 변경의 단일 기준은 Alembic(backend/alembic). create_all은 로컬 MVP 편의용
    # 신규 테이블 생성만 담당하며 기존 테이블 변경은 적용하지 못한다 — 변경은 revision으로.
    Base.metadata.create_all(engine)
    # 재시작으로 중단된 추출·분석·생성 실행을 failed로 정리 — 클라이언트 무한 폴링 방지
    fail_stale_runs()
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


# 독립 results 라우터는 두지 않는다. 현재 리포트는 analysis-runs의 result·generation_result와
# checklist-items를 조합해 제공한다.
