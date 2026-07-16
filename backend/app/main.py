"""FastAPI 진입점.

실행: backend/ 에서 `uvicorn app.main:app --reload`
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.routes import auth, contracts, documents
from app.core.db import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ponytail: Alembic 도입 전 임시 — 테이블이 없으면 만든다 (기존 테이블 변경은 못 함)
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="슬기로운 계약생활 API", version="0.0.0", lifespan=lifespan)

app.include_router(auth.router)
app.include_router(contracts.router)
app.include_router(documents.router)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """공통 오류 형식(docs/api/error-format.md): {"error": {"code", "message"}}."""
    detail = exc.detail if isinstance(exc.detail, dict) else {"code": "error", "message": str(exc.detail)}
    return JSONResponse(status_code=exc.status_code, content={"error": detail}, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """입력 검증 오류(422)도 공통 오류 형식으로 통일한다."""
    # 입력값(input)은 비밀번호 등이 그대로 되돌아갈 수 있어 제외한다
    details = [
        {"loc": e.get("loc"), "msg": e.get("msg"), "type": e.get("type")}
        for e in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "validation_error", "message": "입력값이 올바르지 않습니다.", "details": details}},
    )


@app.get("/health")
def health() -> dict[str, str]:
    """서비스 기동 확인용 헬스체크."""
    return {"status": "ok"}


# TODO: 남은 라우터 등록 (extractions·analyses·results·checklists·feedback)
