"""OpenAI Responses API를 격리한 사용자 안내 생성 provider."""

from __future__ import annotations

import json
import os
from typing import Any

from lease_companion_ai.generation.models import GeneratedGuidanceDraft
from lease_companion_ai.providers.errors import ProviderError
from lease_companion_ai.providers.generation import GenerationRequest


class OpenAIGenerationProvider:
    """고정 모델·호출 한도로 구조화된 안내 초안을 생성한다."""

    model_name = "gpt-5.6-sol"

    def __init__(
        self,
        *,
        client: Any | None = None,
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
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries
        self._max_calls = max_calls
        self._max_output_tokens = max_output_tokens
        self._calls_made = 0

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ProviderError("OpenAI generation provider 설정이 없습니다.")
        try:
            from openai import OpenAI

            self._client = OpenAI(
                api_key=api_key,
                timeout=self._timeout_seconds,
                max_retries=self._max_retries,
            )
        except Exception:
            raise ProviderError(
                "OpenAI generation provider 초기화에 실패했습니다."
            ) from None
        return self._client

    def generate(self, request: GenerationRequest) -> GeneratedGuidanceDraft:
        if self._calls_made >= self._max_calls:
            raise ProviderError("OpenAI generation provider 호출 예산을 초과했습니다.")
        if not request.evidence:
            raise ProviderError("공식 근거 없는 생성 요청은 허용되지 않습니다.")

        self._calls_made += 1
        try:
            response = self._get_client().responses.parse(
                model=self.model_name,
                instructions=(
                    "공식 근거에 한정해 임차인이 직접 확인할 설명, 질문, "
                    "체크리스트와 행동을 작성하십시오. 규칙 판정을 변경하지 마십시오."
                ),
                input=self._serialize_request(request),
                text_format=GeneratedGuidanceDraft,
                max_output_tokens=self._max_output_tokens,
                reasoning={"effort": "low"},
                store=False,
            )
            parsed = getattr(response, "output_parsed", None)
            if parsed is None:
                raise ProviderError("OpenAI generation 응답을 구조화하지 못했습니다.")
            return GeneratedGuidanceDraft.model_validate(parsed)
        except ProviderError:
            raise
        except Exception:
            raise ProviderError("OpenAI generation 호출에 실패했습니다.") from None

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
        }
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)
