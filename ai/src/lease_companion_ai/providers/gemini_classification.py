"""Google GenAI SDK를 격리한 Gemini classification provider."""

from __future__ import annotations

import json
import os
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

from lease_companion_ai.providers.classification import (
    CLASSIFICATION_PROMPT_VERSION,
    load_classification_prompt,
    validate_provider_result,
)
from lease_companion_ai.providers.errors import (
    ProviderError,
    ProviderResponseValidationError,
)
from lease_companion_ai.schemas import (
    ClassificationInput,
    ClassificationMethod,
    ClassificationResult,
    ClauseCandidate,
)


class _ClassificationCandidateBatch(BaseModel):
    """Gemini가 반환할 수 있는 후보 필드만 허용하는 내부 응답 모델."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    candidates: list[ClauseCandidate]


class GeminiClassificationProvider:
    model_name = "gemini-3.5-flash"

    def __init__(
        self,
        *,
        client: Any | None = None,
        prompt: str | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds는 양수여야 합니다.")
        self._client = client
        self._prompt = prompt or load_classification_prompt()
        self._timeout_seconds = timeout_seconds

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ProviderError("Gemini classification provider 설정이 없습니다.")
        try:
            from google import genai
            from google.genai import types

            self._client = genai.Client(
                api_key=api_key,
                http_options=types.HttpOptions(
                    timeout=int(self._timeout_seconds * 1_000)
                ),
            )
        except Exception:
            raise ProviderError(
                "Gemini classification provider 초기화에 실패했습니다."
            ) from None
        return self._client

    def classify(
        self, classification_input: ClassificationInput
    ) -> ClassificationResult:
        try:
            from google.genai import types

            response = self._get_client().models.generate_content(
                model=self.model_name,
                contents=[self._prompt, self._serialize_input(classification_input)],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=_ClassificationCandidateBatch,
                    temperature=0,
                ),
            )
            parsed = getattr(response, "parsed", None)
            if parsed is None:
                raise ProviderResponseValidationError(
                    "classification provider 응답 검증에 실패했습니다."
                )
            try:
                batch = _ClassificationCandidateBatch.model_validate(parsed)
                result = ClassificationResult(
                    schema_version=classification_input.schema_version,
                    input_snapshot_id=classification_input.input_snapshot_id,
                    contract_id=classification_input.contract_id,
                    provider_model=f"gemini/{self.model_name}",
                    prompt_version=CLASSIFICATION_PROMPT_VERSION,
                    classification_method=ClassificationMethod.PROVIDER,
                    candidates=batch.candidates,
                )
            except (TypeError, ValueError, ValidationError):
                raise ProviderResponseValidationError(
                    "classification provider 응답 검증에 실패했습니다."
                ) from None
            return validate_provider_result(classification_input, result)
        except ProviderError:
            raise
        except Exception:
            raise ProviderError("Gemini classification 호출에 실패했습니다.") from None

    @staticmethod
    def _serialize_input(classification_input: ClassificationInput) -> str:
        payload = {
            "schema_version": classification_input.schema_version,
            "clauses": [
                {
                    "clause_ref": clause.clause_ref,
                    "source_field": clause.source_field.value,
                    "ordinal": clause.ordinal,
                    "text": clause.text,
                }
                for clause in classification_input.clauses
            ],
        }
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)
