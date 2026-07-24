"""Google GenAI SDK를 격리한 사용자 안내 생성 provider."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from lease_companion_ai.generation.models import (
    GeneratedGuidanceBatch,
    GeneratedGuidanceDraft,
)
from lease_companion_ai.providers.errors import ProviderError
from lease_companion_ai.providers.gemini_gateway import (
    GeminiCallPolicy,
    GeminiGateway,
    gemini_http_options,
    get_gemini_gateway,
)
from lease_companion_ai.providers.gemini_schema import clean_gemini_response_schema
from lease_companion_ai.providers.generation import GenerationRequest


logger = logging.getLogger(__name__)

_GEMINI_RESPONSE_SCHEMA = clean_gemini_response_schema(
    GeneratedGuidanceDraft.model_json_schema()
)
_BATCH_RESPONSE_SCHEMA = clean_gemini_response_schema(
    GeneratedGuidanceBatch.model_json_schema()
)
# 한 항목의 안내(설명·질문·수정요청·체크리스트·행동)에 필요한 출력 토큰 근사치.
# 배치 크기와 무관하게 max_output_tokens를 고정하면 항목이 늘어날수록 응답이 잘려
# 배치 전체가 검증에 실패하고 전 항목이 템플릿 폴백이 된다(2026-07-23 실측).
_OUTPUT_TOKENS_PER_ITEM = 400
_BATCH_OUTPUT_TOKEN_CEILING = 8_192


def _finish_reason(response: Any) -> str:
    """응답 종료 사유만 안전하게 뽑는다. SDK 구조가 달라도 예외를 내지 않는다."""
    try:
        candidate = (getattr(response, "candidates", None) or [None])[0]
        reason = getattr(candidate, "finish_reason", None)
        return str(getattr(reason, "name", reason) or "unknown")
    except Exception:
        return "unknown"


class GeminiGenerationProvider:
    """고정 모델·호출 한도로 구조화된 안내 초안을 생성한다."""

    model_name = "gemini-3.5-flash"

    def __init__(
        self,
        *,
        client: Any | None = None,
        gateway: GeminiGateway | None = None,
        timeout_seconds: float = 30.0,
        max_retries: int = 2,
        max_calls: int = 10,
        max_output_tokens: int = 1_500,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds는 양수여야 합니다.")
        if max_retries < 0:
            raise ValueError("max_retries는 0 이상이어야 합니다.")
        if max_calls <= 0:
            raise ValueError("max_calls는 양수여야 합니다.")
        if max_output_tokens <= 0:
            raise ValueError("max_output_tokens는 양수여야 합니다.")
        self._client = client
        self.model_name = os.getenv("GEMINI_MODEL_GENERATION", type(self).model_name)
        self._gateway = gateway or get_gemini_gateway()
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._max_calls = max_calls
        self._max_output_tokens = max_output_tokens
        self._calls_made = 0

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ProviderError("Gemini generation provider 설정이 없습니다.")
        try:
            from google import genai

            self._client = genai.Client(
                api_key=api_key,
                http_options=gemini_http_options(int(self._timeout_seconds * 1_000)),
            )
        except Exception:
            raise ProviderError(
                "Gemini generation provider 초기화에 실패했습니다."
            ) from None
        return self._client

    def generate(self, request: GenerationRequest) -> GeneratedGuidanceDraft:
        if self._calls_made >= self._max_calls:
            raise ProviderError("Gemini generation provider 호출 예산을 초과했습니다.")
        if not request.evidence:
            raise ProviderError("공식 근거 없는 생성 요청은 허용되지 않습니다.")

        self._calls_made += 1
        try:
            from google.genai import types

            response = self._gateway.call(
                task="report_generation",
                model=self.model_name,
                policy=GeminiCallPolicy(
                    max_attempts=self._max_retries + 1,
                    max_total_wait_seconds=15.0,
                ),
                operation=lambda: self._get_client().models.generate_content(
                    model=self.model_name,
                    contents=[
                        (
                            "공식 근거에 한정해 임차인이 직접 확인할 설명, 질문, "
                            "수정 요청 또는 체크리스트와 행동을 작성하십시오. "
                            "규칙 판정을 변경하거나 법률 결론을 단정하지 마십시오."
                        ),
                        self._serialize_request(request),
                    ],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=_GEMINI_RESPONSE_SCHEMA,
                        temperature=0,
                        max_output_tokens=self._max_output_tokens,
                        # gemini-3.5-flash는 thinking 모델 — thinking이 max_output_tokens를
                        # 소진해 답변이 잘리고 비용도 커지므로 구조화 생성에는 thinking을 끈다.
                        thinking_config=types.ThinkingConfig(thinking_budget=0),
                    ),
                ),
            )
        except ProviderError:
            raise
        except Exception:
            raise ProviderError("Gemini generation 호출에 실패했습니다.") from None
        try:
            parsed = getattr(response, "parsed", None)
            if parsed is not None:
                return GeneratedGuidanceDraft.model_validate(parsed)
            text = getattr(response, "text", None)
            if text:
                return GeneratedGuidanceDraft.model_validate_json(text)
        except Exception:
            raise ProviderError("Gemini generation 응답 검증에 실패했습니다.") from None
        raise ProviderError("Gemini generation 응답이 비어 있습니다.")

    @property
    def _items_per_call(self) -> int:
        """한 호출에 담을 항목 수. 출력 토큰 예산으로 나눈다."""
        return max(1, self._max_output_tokens // _OUTPUT_TOKENS_PER_ITEM)

    def generate_batch(
        self, requests: tuple[GenerationRequest, ...]
    ) -> dict[str, GeneratedGuidanceDraft]:
        """요청을 출력 예산에 맞게 나눠 호출하고 결과를 합친다.

        한 번에 전부 보내면 응답이 잘려 배치 전체가 무효가 되고 모든 항목이
        템플릿 폴백으로 떨어진다. 청크 하나가 실패해도 나머지 청크 결과는 살린다.
        """
        if not requests:
            return {}
        if any(not request.evidence for request in requests):
            raise ProviderError("공식 근거 없는 생성 요청은 허용되지 않습니다.")

        size = self._items_per_call
        chunks = [
            requests[start : start + size] for start in range(0, len(requests), size)
        ]
        outputs: dict[str, GeneratedGuidanceDraft] = {}
        failures: list[str] = []
        for index, chunk in enumerate(chunks, start=1):
            try:
                outputs.update(self._generate_chunk(chunk))
            except ProviderError as exc:
                failures.append(str(exc))
                logger.warning(
                    "배치 청크 실패 %d/%d 항목=%d: %s",
                    index,
                    len(chunks),
                    len(chunk),
                    exc,
                )
        if not outputs and failures:
            raise ProviderError(failures[0])
        return outputs

    def _generate_chunk(
        self, requests: tuple[GenerationRequest, ...]
    ) -> dict[str, GeneratedGuidanceDraft]:
        if self._calls_made >= self._max_calls:
            raise ProviderError("Gemini generation provider 호출 예산을 초과했습니다.")
        self._calls_made += 1
        try:
            from google.genai import types

            response = self._gateway.call(
                task="report_generation",
                model=self.model_name,
                policy=GeminiCallPolicy(
                    max_attempts=self._max_retries + 1,
                    max_total_wait_seconds=15.0,
                ),
                operation=lambda: self._get_client().models.generate_content(
                    model=self.model_name,
                    contents=[
                        "각 ID별로 공식 근거에 한정한 안내를 작성하십시오.",
                        self._serialize_batch(requests),
                    ],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=_BATCH_RESPONSE_SCHEMA,
                        temperature=0,
                        max_output_tokens=min(
                            _BATCH_OUTPUT_TOKEN_CEILING,
                            max(
                                self._max_output_tokens,
                                len(requests) * _OUTPUT_TOKENS_PER_ITEM,
                            ),
                        ),
                        thinking_config=types.ThinkingConfig(thinking_budget=0),
                    ),
                ),
            )
        except ProviderError:
            raise
        except Exception:
            raise ProviderError("Gemini generation 호출에 실패했습니다.") from None
        try:
            parsed = getattr(response, "parsed", None)
            batch = (
                GeneratedGuidanceBatch.model_validate(parsed)
                if parsed is not None
                else GeneratedGuidanceBatch.model_validate_json(response.text)
            )
        except Exception:
            # 잘림(MAX_TOKENS)인지 스키마 불일치인지 구분해야 재발을 막을 수 있다.
            # 응답 원문은 남기지 않고 종료 사유만 남긴다.
            logger.warning(
                "배치 응답 검증 실패 항목=%d finish_reason=%s",
                len(requests),
                _finish_reason(response),
            )
            raise ProviderError("Gemini generation 응답 검증에 실패했습니다.") from None
        requested_ids = {request.rule_id for request in requests}
        outputs: dict[str, GeneratedGuidanceDraft] = {}
        for item in batch.items:
            if item.item_id in requested_ids and item.item_id not in outputs:
                outputs[item.item_id] = item.as_draft()
        return outputs

    @staticmethod
    def _serialize_request(request: GenerationRequest) -> str:
        payload = {
            "prompt_version": request.prompt_version,
            "rule": {
                "rule_id": request.rule_id,
                "rule_name": request.rule_name,
                "status": request.status,
                "urgency": request.urgency,
                "reason": request.reason,
                "limitations": request.limitations,
            },
            "official_evidence": [
                {
                    "source_id": evidence.source_id,
                    "title": evidence.title,
                    "institution": evidence.institution,
                    "summary": evidence.summary,
                    "source_url": evidence.source_url,
                }
                for evidence in request.evidence
            ],
            "prompts": dict(request.prompts),
            "deidentified_clause_text": request.deidentified_clause_text,
        }
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)

    @classmethod
    def _serialize_batch(cls, requests: tuple[GenerationRequest, ...]) -> str:
        return json.dumps(
            {
                "items": [
                    json.loads(cls._serialize_request(request)) for request in requests
                ]
            },
            ensure_ascii=False,
            sort_keys=True,
        )
