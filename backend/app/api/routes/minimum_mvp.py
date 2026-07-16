"""최소 MVP 데모용 API 라우트."""

from fastapi import APIRouter, HTTPException, status

from app.schemas.minimum_mvp import AnalysisRequest, AnalysisResponse, ExtractionRequest, ExtractionResponse
from app.services import minimum_mvp as service


router = APIRouter(prefix="/api/minimum-mvp", tags=["minimum-mvp"])


@router.post("/extract", response_model=ExtractionResponse)
def extract_documents(request: ExtractionRequest) -> ExtractionResponse:
    try:
        return ExtractionResponse.model_validate(service.extract(request))
    except service.MinimumMvpInputError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "document_processing_failed", "message": str(exc)},
        ) from exc


@router.post("/analyze", response_model=AnalysisResponse)
def analyze_documents(request: AnalysisRequest) -> AnalysisResponse:
    try:
        results = service.analyze(request)
    except service.MinimumMvpInputError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "extraction_not_confirmed", "message": str(exc)},
        ) from exc
    return AnalysisResponse(
        results=results,
        disclaimer="이 결과는 계약 가능·안전·적법 여부를 확정하지 않습니다. 문서에서 추가로 확인할 항목과 질문·행동을 안내합니다.",
    )
