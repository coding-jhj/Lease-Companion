"""상용 LLM(Gemini) 구조화 추출 — 텍스트 또는 스캔 원본 → 고정 스키마 JSON.

디지털 텍스트는 텍스트 구조화로, 스캔 PDF·이미지는 원본을 직접 구조화하는 1회 VLM 호출로 처리한다.
정규식 파서(minimum_mvp.py)는 실제 서식(폼 레이아웃)에서 필드를 못 뽑아 이걸로 대체하며,
키 없음·API 실패 시 그 정규식 파서로 폴백한다(pipelines/minimum_mvp.py).

response_schema(pydantic)로 필드명·타입·enum·tri-state(null)를 강제해 run_rules 계약을 지킨다.
프롬프트는 ai/prompts/extraction/ 에서 로드(AGENTS.md: 프롬프트 버전관리).

"""
from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from threading import BoundedSemaphore, Lock
from typing import Any, Literal, Optional

from pydantic import BaseModel

from lease_companion_ai.providers.errors import ProviderError
from lease_companion_ai.ingestion.limits import (
    MAX_CONCURRENT_VLM_CALLS,
    MAX_EXTERNAL_CALLS_PER_REQUEST,
)
from lease_companion_ai.guardrails.pii import PiiTokenizer, contains_raw_pii

logger = logging.getLogger(__name__)

_MODEL = "gemini-3.5-flash"
_MAX_STRUCTURE_ATTEMPTS = 4  # 일시 503 백오프 재시도 횟수 (스캔 VLM 구조화용)
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
    agent_relationship: Optional[str] = None
    proxy_authority_documents: Optional[list[str]] = None
    deposit_korean_amount: Optional[int] = None
    monthly_rent_korean_amount: Optional[int] = None
    contract_payment_korean_amount: Optional[int] = None
    balance_payment_korean_amount: Optional[int] = None
    contract_payment_date: Optional[str] = None
    balance_payment_date: Optional[str] = None
    management_fee_present: Optional[bool] = None
    management_fee: Optional[int] = None
    management_fee_items: Optional[list[str]] = None
    deposit_return_clause: Optional[str] = None
    repair_responsibility_clause: Optional[str] = None
    main_clauses: Optional[list[str]] = None
    special_clauses_present: Optional[bool] = None
    special_clauses: Optional[list[str]] = None


class RegistryFields(BaseModel):
    owner_names: Optional[list[str]]
    is_joint_ownership: Optional[bool]
    property_address: Optional[str]
    issue_date: Optional[str]
    mortgage_present: Optional[bool]              # tri-state: null=판독불가·미확인
    seizure_present: Optional[bool]
    provisional_seizure_present: Optional[bool]
    trust_present: Optional[bool]
    owner_shares: Optional[dict[str, str]] = None


class GeminiExtractError(ProviderError):
    """구조화 추출 불가(키 미설정·SDK 미설치·API 실패)."""


class ExternalCallBudget:
    """한 사용자 요청에서 실행할 수 있는 외부 호출 수를 제한한다."""

    def __init__(self, maximum: int = MAX_EXTERNAL_CALLS_PER_REQUEST) -> None:
        self._remaining = maximum
        self._lock = Lock()

    def consume(self) -> None:
        with self._lock:
            if self._remaining <= 0:
                raise GeminiExtractError("요청당 외부 호출 한도를 초과했습니다.")
            self._remaining -= 1


_VLM_SEMAPHORE = BoundedSemaphore(MAX_CONCURRENT_VLM_CALLS)


def _client():
    # 구조화 추출 전용 SDK 경계. 검색·생성 provider와 책임을 섞지 않는다.
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


def _clean_response_schema(node: Any) -> Any:
    """Gemini response_schema가 거부하는 키(additionalProperties·title·default)를 제거한다.

    Pydantic이 낸 JSON Schema를 그대로 넘기면, dict 필드(예: RegistryFields.owner_shares)의
    `additionalProperties` 때문에 400 INVALID_ARGUMENT가 난다. 지원되는 하위 집합만 남긴다.
    (생성 provider와 동일 기법)
    """
    if isinstance(node, dict):
        return {
            key: _clean_response_schema(value)
            for key, value in node.items()
            if key not in ("additionalProperties", "title", "default")
        }
    if isinstance(node, list):
        return [_clean_response_schema(item) for item in node]
    return node


def _generation_config(schema: type[BaseModel]):
    from google.genai import types

    return types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=_clean_response_schema(schema.model_json_schema()),
        # 필드 옮기기는 복잡한 추론이 아니므로 Gemini 3.x 권장 수준 중 최소값을 쓴다.
        thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.MINIMAL),
    )


def _generate(contents: list, schema: type[BaseModel], budget: ExternalCallBudget | None = None) -> dict:
    client = _client()
    from google.genai import errors
    if budget is not None:
        budget.consume()
    config = _generation_config(schema)
    # 스캔 PDF·이미지 VLM 구조화는 한 번에 26~40초 걸려 일시 503(ServerError)이 흔하다.
    # 재시도 없이 바로 실패로 떨어지면 정상 문서도 "구조화 API 오류"가 된다 —
    # 일시 장애는 백오프 재시도하고, 4xx·쿼터(APIError)만 즉시 실패시킨다.
    for attempt in range(_MAX_STRUCTURE_ATTEMPTS):
        try:
            with _VLM_SEMAPHORE:
                resp = client.models.generate_content(
                    model=_MODEL,
                    contents=contents,
                    config=config,
                )
            break
        except errors.ServerError as exc:
            # 로그는 원인 특정용 — 예외 종류·상태코드만(문서 내용 아님).
            logger.warning(
                "구조화 추출 일시 오류(재시도 %d/%d): %s code=%s",
                attempt + 1, _MAX_STRUCTURE_ATTEMPTS, type(exc).__name__,
                getattr(exc, "code", None),
            )
            if attempt == _MAX_STRUCTURE_ATTEMPTS - 1:
                raise GeminiExtractError("구조화 추출 API 오류가 발생했습니다.") from exc
            time.sleep(5 * (attempt + 1))
        except errors.APIError as exc:  # 4xx·쿼터 등 비재시도
            # message는 원인 특정에 필요한 API 메타데이터(문서 내용 아님) — 앞부분만 남긴다.
            detail = (getattr(exc, "message", None) or str(exc))[:300]
            logger.error(
                "구조화 추출 API 오류(비재시도): %s code=%s status=%s detail=%s",
                type(exc).__name__, getattr(exc, "code", None),
                getattr(exc, "status", None), detail,
            )
            raise GeminiExtractError("구조화 추출 API 오류가 발생했습니다.") from exc
        except Exception as exc:
            logger.exception("구조화 추출 호출 실패: %s", type(exc).__name__)
            raise GeminiExtractError("구조화 추출 호출에 실패했습니다.") from exc

    parsed = resp.parsed
    if isinstance(parsed, schema):
        return parsed.model_dump()
    if resp.text:  # parsed가 비면 원문 JSON을 스키마로 재검증
        try:
            return schema.model_validate_json(resp.text).model_dump()
        except Exception as exc:
            raise GeminiExtractError(
                "구조화 추출 결과가 스키마와 일치하지 않습니다."
            ) from exc
    raise GeminiExtractError("구조화 추출 결과가 비어 있습니다.")


def _extract(text: str, prompt_file: str, schema: type[BaseModel]) -> dict:
    tokenizer = PiiTokenizer()
    deidentified = tokenizer.tokenize(text)
    if deidentified is None or contains_raw_pii(deidentified):
        raise GeminiExtractError("개인정보 비식별화에 실패했습니다.")
    prompt = (_PROMPTS / prompt_file).read_text(encoding="utf-8").replace(
        "{text}", deidentified
    )
    return _restore_values(_generate([prompt], schema), tokenizer)


def _restore_values(value: Any, tokenizer: PiiTokenizer) -> Any:
    if isinstance(value, str):
        return tokenizer.restore(value)
    if isinstance(value, list):
        return [_restore_values(item, tokenizer) for item in value]
    if isinstance(value, dict):
        return {key: _restore_values(item, tokenizer) for key, item in value.items()}
    return value


def extract_contract_fields(text: str) -> dict:
    return _extract(text, "contract_fields.txt", ContractFields)


def extract_registry_fields(text: str) -> dict:
    return _extract(text, "registry_fields.txt", RegistryFields)


def extract_scanned_fields(
    content: bytes,
    mime_type: str,
    doc_type: Literal["contract", "registry"],
    *,
    budget: ExternalCallBudget,
) -> dict:
    """스캔 PDF·이미지 원본을 평문 OCR 단계 없이 한 번에 구조화한다."""
    try:
        from google.genai import types
    except ImportError as exc:
        raise GeminiExtractError("구조화 추출에 google-genai가 필요합니다.") from exc

    prompt_file = "contract_fields.txt" if doc_type == "contract" else "registry_fields.txt"
    schema: type[BaseModel] = ContractFields if doc_type == "contract" else RegistryFields
    prompt = (_PROMPTS / prompt_file).read_text(encoding="utf-8")
    prompt = prompt.split("문서 텍스트:", 1)[0] + "첨부 문서에서 위 필드를 직접 추출하라."
    return _generate(
        [prompt, types.Part.from_bytes(data=content, mime_type=mime_type)],
        schema,
        budget,
    )
