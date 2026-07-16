"""FastAPI 앱들이 공유하는 외부 오류 응답 형식."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, HTTPException):
        raise exc
    detail = exc.detail
    if isinstance(detail, dict):
        error = {
            "code": str(detail.get("code", "http_error")).lower(),
            "message": str(detail.get("message", "요청을 처리할 수 없습니다.")),
        }
        if "details" in detail:
            error["details"] = detail["details"]
    else:
        error = {"code": "http_error", "message": str(detail)}
    return JSONResponse(status_code=exc.status_code, content={"error": error}, headers=exc.headers)


async def validation_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):
        raise exc
    # exc.body와 errors()[].input은 비밀번호·문서 본문·base64를 포함할 수 있어 반환하지 않는다.
    details = [
        {"loc": error.get("loc"), "msg": error.get("msg"), "type": error.get("type")}
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "validation_error",
                "message": "입력값이 올바르지 않습니다.",
                "details": details,
            }
        },
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
