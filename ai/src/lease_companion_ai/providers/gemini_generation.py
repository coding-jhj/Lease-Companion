"""Google GenAI SDK를 격리한 사용자 안내 생성 provider."""

from __future__ import annotations

import json
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
from lease_companion_ai.providers.generation import GenerationRequest


def _clean_response_schema(node: Any) -> Any:
    """Gemini response_schema가 거부하는 키(additionalProperties·title·default)를 제거한다.

    Pydantic이 생성한 JSON Schema를 그대로 넘기면 `additionalProperties` 때문에
    400 INVALID_ARGUMENT가 발생하므로 지원되는 하위 집합만 남긴다.
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


_GEMINI_RESPONSE_SCHEMA = _clean_response_schema(
    GeneratedGuidanceDraft.model_json_schema()
)


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

    def generate_batch(
        self, requests: tuple[GenerationRequest, ...]
    ) -> dict[str, GeneratedGuidanceDraft]:
        if not requests:
            return {}
        if any(not request.evidence for request in requests):
            raise ProviderError("공식 근거 없는 생성 요청은 허용되지 않습니다.")
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
                        response_schema=_clean_response_schema(
                            GeneratedGuidanceBatch.model_json_schema()
                        ),
                        temperature=0,
                        max_output_tokens=self._max_output_tokens,
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
