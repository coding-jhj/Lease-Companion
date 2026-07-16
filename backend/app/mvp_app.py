"""최소 MVP 브라우저 데모용 FastAPI 진입점."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes.minimum_mvp import router as minimum_mvp_router
from app.core.errors import register_error_handlers


app = FastAPI(title="슬기로운 계약생활 최소 MVP", version="0.1.0")
register_error_handlers(app)
static_dir = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")
app.include_router(minimum_mvp_router)


@app.get("/", include_in_schema=False)
def demo() -> FileResponse:
    return FileResponse(static_dir / "index.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
