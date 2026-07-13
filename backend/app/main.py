"""FastAPI 진입점.

현재는 헬스체크 스텁만 제공한다. 실제 엔드포인트(세션·업로드·분석·결과)는
`app/api/routes/` 에서 구현 예정. 실행 명령은 서버 런타임 확정 후 README에 기록한다.
"""

from fastapi import FastAPI

app = FastAPI(title="슬기로운 계약생활 API", version="0.0.0")


@app.get("/health")
def health() -> dict[str, str]:
    """서비스 기동 확인용 헬스체크."""
    return {"status": "ok"}


# TODO: api/routes 라우터 등록 (계약 단계·업로드·추출 확인·분석·결과 리포트)
# TODO: core 설정(.env 로드)·공통 오류 핸들러 연결
