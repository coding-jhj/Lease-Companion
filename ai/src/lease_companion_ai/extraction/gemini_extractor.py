"""상용 LLM(Gemini) 구조화 추출 — 문서 텍스트 → 고정 스키마 필드 JSON.

OCR/PyMuPDF가 낸 **텍스트**를 입력받아 계약·등기 필드를 구조화한다(결정: OCR·구조화 = Gemini).
정규식 파서(minimum_mvp.py)는 실제 서식(폼 레이아웃)에서 필드를 못 뽑아 이걸로 대체하며,
키 없음·API 실패 시 그 정규식 파서로 폴백한다(pipelines/minimum_mvp.py).

response_schema(pydantic)로 필드명·타입·enum·tri-state(null)를 강제해 run_rules 계약을 지킨다.
프롬프트는 ai/prompts/extraction/ 에서 로드(AGENTS.md: 프롬프트 버전관리).

ponytail: 스캔 문서는 (OCR→텍스트)+(구조화) 2콜이 된다. VLM 이미지 단일콜 통합은 처리량이
필요해지면 도입. 지금은 텍스트 단일경로로 표면을 최소화한다.
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel

_MODEL = "gemini-3.5-flash"
_PROMPTS = Path(__file__).resolve().parents[3] / "prompts" / "extraction"

ClarityStatus = Literal["명확", "불명확", "미기재", "확인 필요"]


class ContractFields(BaseModel):
    contract_type: Optional[str]
    landlord_name: Optional[str]
    tenant_name: Optional[str]
    agent_name: Optional[str]
    property_address: Optional[str]
    deposit: Optional[int]
    monthly_rent: Optional[int]
    contract_payment: Optional[int]
    balance_payment: Optional[int]
    account_holder: Optional[str]
    start_date: Optional[str]
    end_date: Optional[str]
    move_in_date: Optional[str]
    deposit_return_condition: ClarityStatus
    repair_responsibility: ClarityStatus
    rights_change_clause_present: bool


class RegistryFields(BaseModel):
    owner_names: Optional[list[str]]
    is_joint_ownership: Optional[bool]
    property_address: Optional[str]
    issue_date: Optional[str]
    mortgage_present: Optional[bool]              # tri-state: null=판독불가·미확인
    seizure_present: Optional[bool]
    provisional_seizure_present: Optional[bool]
    trust_present: Optional[bool]


class GeminiExtractError(RuntimeError):
    """구조화 추출 불가(키 미설정·SDK 미설치·API 실패)."""


def _client():
    # ponytail: ingestion/ocr.py와 동일 패턴(작은 중복). 공용화하려면 providers/gemini.py로.
    envf = Path(__file__).resolve().parents[4] / ".env"  # …/extraction/gemini_extractor.py → repo root
    if envf.exists():
        for line in envf.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        raise GeminiExtractError("구조화 추출용 GEMINI_API_KEY가 설정되지 않았습니다.")
    try:
        from google import genai
    except ImportError as exc:
        raise GeminiExtractError("구조화 추출에 google-genai가 필요합니다.") from exc
    return genai.Client(api_key=key)


def _extract(text: str, prompt_file: str, schema: type[BaseModel]) -> dict:
    client = _client()
    from google.genai import errors, types

    prompt = (_PROMPTS / prompt_file).read_text(encoding="utf-8").replace("{text}", text)
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=schema,
        # 고정 스키마 필드 추출에 thinking 불필요 — 끄면 지연 대폭 감소(OCR 실측 5.8배).
        # 품질은 E2E 필드 비교로 확인. 복잡 문서에서 필드 오추출이 늘면 이 줄만 제거.
        thinking_config=types.ThinkingConfig(thinking_budget=0),
    )
    # 503 등 일시 장애는 재시도(ocr.py와 동일 패턴). 재시도 없이 바로 정규식 폴백으로
    # 떨어지면 스캔 문서에서 쓰레기 필드가 나온다 — 폴백은 최후, 재시도가 먼저다.
    for attempt in range(4):
        try:
            resp = client.models.generate_content(model=_MODEL, contents=[prompt], config=config)
            break
        except errors.ServerError as exc:
            if attempt == 3:
                raise GeminiExtractError(f"구조화 추출 API 호출 실패: {exc}") from exc
            time.sleep(5 * (attempt + 1))
        except errors.APIError as exc:  # 4xx·쿼터 등 비재시도
            raise GeminiExtractError(f"구조화 추출 API 오류: {exc}") from exc

    parsed = resp.parsed
    if isinstance(parsed, schema):
        return parsed.model_dump()
    if resp.text:  # parsed가 비면 원문 JSON을 스키마로 재검증
        return schema.model_validate_json(resp.text).model_dump()
    raise GeminiExtractError("구조화 추출 결과가 비어 있습니다.")


def extract_contract_fields(text: str) -> dict:
    return _extract(text, "contract_fields.txt", ContractFields)


def extract_registry_fields(text: str) -> dict:
    return _extract(text, "registry_fields.txt", RegistryFields)
