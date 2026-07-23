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
from pathlib import Path

from threading import BoundedSemaphore, Lock
from typing import Any, Literal, Optional

from pydantic import BaseModel

from lease_companion_ai.providers.errors import (
    ProviderError,
    ProviderTemporaryError,
    ProviderTimeoutError,
)
from lease_companion_ai.providers.gemini_gateway import (
    GeminiCallPolicy,
    gemini_http_options,
    get_gemini_gateway,
)
from lease_companion_ai.providers.gemini_schema import clean_gemini_response_schema
from lease_companion_ai.ingestion.limits import (
    MAX_CONCURRENT_VLM_CALLS,
    MAX_EXTERNAL_CALLS_PER_REQUEST,
)
from lease_companion_ai.guardrails.pii import PiiTokenizer, contains_raw_pii

logger = logging.getLogger(__name__)

_MODEL = "gemini-3.5-flash"
# 주 모델이 과부하(503/504·타임아웃)로 재시도가 소진되면 이 대체 모델로 폴백한다.
# (플레인 gemini-3.1-flash는 API에 없음 — 실재하는 flash 계층 3.1은 flash-lite다.)
_FALLBACK_MODEL = "gemini-3.1-flash-lite"
_MAX_STRUCTURE_ATTEMPTS = 2
# 스캔 VLM 구조화는 26~40초 걸린다. 타임아웃을 명시하지 않으면 SDK 기본값에 걸려
# 응답 전에 클라이언트가 끊고(서버 로그 499 Client Closed Request) 추출이 실패한다.
_HTTP_TIMEOUT_MS = 60_000
_PROMPTS = Path(__file__).resolve().parents[3] / "prompts" / "extraction"

ClarityStatus = Literal["명확", "불명확", "미기재", "확인 필요"]


class ContractFields(BaseModel):
    contract_type: Optional[str]
    landlord_name: Optional[str]
    tenant_name: Optional[str]
    agent_name: Optional[str]
    property_address: Optional[str]
    building_use: Optional[str] = None
    deposit: Optional[int]
    monthly_rent: Optional[int]
    contract_payment: Optional[int]
    balance_payment: Optional[int]
    account_holder: Optional[str]
    # 입금 계좌 표시용(판정 미사용). 예금주 미기재라도 계좌번호·은행명은 따로 보존한다.
    account_number: Optional[str] = None
    bank_name: Optional[str] = None
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
    ground_right_present: Optional[bool] = None


class GeminiExtractError(ProviderError):
    """구조화 추출 불가(키 미설정·SDK 미설치·API 실패)."""


class _TransientExtractError(GeminiExtractError):
    """일시 장애(503/504·타임아웃)로 재시도가 소진됨 — 대체 모델 폴백 대상."""


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
    return genai.Client(
        api_key=key,
        http_options=gemini_http_options(_HTTP_TIMEOUT_MS),
    )


def _generation_config(schema: type[BaseModel]):
    from google.genai import types

    return types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=clean_gemini_response_schema(schema.model_json_schema()),
        # 필드 옮기기는 복잡한 추론이 아니므로 Gemini 3.x 권장 수준 중 최소값을 쓴다.
        thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.MINIMAL),
    )


def _generate(contents: list, schema: type[BaseModel], budget: ExternalCallBudget | None = None) -> dict:
    client = _client()
    if budget is not None:
        budget.consume()
    config = _generation_config(schema)
    # 주 모델이 과부하로 재시도까지 소진되면 대체 모델로 폴백한다. 4xx·스키마 오류 등
    # 비일시 실패는 폴백해도 같으므로 그대로 던진다.
    models = (os.getenv("GEMINI_MODEL_EXTRACTION", _MODEL), _FALLBACK_MODEL)
    for index, model in enumerate(models):
        try:
            return _parse_response(_call_with_retries(client, model, contents, config), schema)
        except _TransientExtractError:
            if index == len(models) - 1:
                raise
            logger.warning("주 모델(%s) 과부하 — 대체 모델(%s)로 폴백", model, models[index + 1])
    raise _TransientExtractError("구조화 추출 API 오류가 발생했습니다.")  # 도달 불가


def _call_with_retries(client: Any, model: str, contents: list, config: Any):
    """공용 Gateway를 통해 한 모델을 제한적으로 호출한다."""
    try:
        return get_gemini_gateway().call(
            task="document_extraction",
            model=model,
            policy=GeminiCallPolicy(
                max_attempts=_MAX_STRUCTURE_ATTEMPTS,
                max_total_wait_seconds=15.0,
            ),
            operation=lambda: _call_extraction_model(client, model, contents, config),
        )
    except (ProviderTemporaryError, ProviderTimeoutError) as exc:
        raise _TransientExtractError("구조화 추출 API 오류가 발생했습니다.") from exc
    except ProviderError as exc:
        raise GeminiExtractError("구조화 추출 API 오류가 발생했습니다.") from exc


def _call_extraction_model(client: Any, model: str, contents: list, config: Any):
    with _VLM_SEMAPHORE:
        return client.models.generate_content(
            model=model, contents=contents, config=config
        )


def _parse_response(resp: Any, schema: type[BaseModel]) -> dict:
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
