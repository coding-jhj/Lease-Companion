"""승인 사실 기반 계약 연습 NPC 대사를 생성하는 Gemini adapter."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from lease_companion_ai.providers.errors import (
    ProviderError,
    ProviderResponseValidationError,
)
from lease_companion_ai.providers.gemini_gateway import (
    GeminiCallPolicy,
    GeminiGateway,
    gemini_http_options,
    get_gemini_gateway,
)
from lease_companion_ai.providers.gemini_schema import clean_gemini_response_schema
from lease_companion_ai.schemas.simulation import ScenarioDefinition
from lease_companion_ai.simulation.dialogue_provider import (
    DialogueGenerationRequest,
    DialogueGenerationResult,
    PracticeDialogueProvider,
)


_DIALOGUE_RESPONSE_SCHEMA = clean_gemini_response_schema(
    DialogueGenerationResult.model_json_schema()
)


def load_practice_dialogue_prompt(root: Path | None = None) -> str:
    prompt_root = root or Path(__file__).resolve().parents[3] / "prompts"
    prompt = (prompt_root / "simulation" / "dialogue-v1.txt").read_text(
        encoding="utf-8"
    )
    if not prompt.strip() or prompt.splitlines()[0].strip() != (
        "버전: practice-dialogue-v1"
    ):
        raise ValueError("연습 대사 프롬프트 헤더는 practice-dialogue-v1이어야 합니다.")
    return prompt


class GeminiPracticeDialogueProvider:
    model_name = "gemini-3.5-flash"

    def __init__(
        self,
        *,
        client: Any | None = None,
        gateway: GeminiGateway | None = None,
        api_key: str | None = None,
        prompt: str | None = None,
        timeout_seconds: float = 30.0,
        max_output_tokens: int = 300,
    ) -> None:
        self._client = client
        self._gateway = gateway or get_gemini_gateway()
        self._api_key = api_key
        self._prompt = prompt or load_practice_dialogue_prompt()
        self._timeout_seconds = timeout_seconds
        self._max_output_tokens = max_output_tokens
        self.model_name = os.getenv("GEMINI_MODEL_PRACTICE", type(self).model_name)

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        api_key = (
            self._api_key
            or os.getenv("GEMINI_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
        )
        if not api_key:
            raise ProviderError("Gemini practice dialogue provider 설정이 없습니다.")
        try:
            from google import genai

            self._client = genai.Client(
                api_key=api_key,
                http_options=gemini_http_options(int(self._timeout_seconds * 1_000)),
            )
        except Exception:
            raise ProviderError(
                "Gemini practice dialogue provider 초기화에 실패했습니다."
            ) from None
        return self._client

    def generate(
        self, request: DialogueGenerationRequest
    ) -> DialogueGenerationResult:
        try:
            from google.genai import types

            config = types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=_DIALOGUE_RESPONSE_SCHEMA,
                temperature=0,
                max_output_tokens=self._max_output_tokens,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            )
            response = self._gateway.call(
                task=(
                    "practice_dialogue_regeneration"
                    if request.correction_codes
                    else "practice_dialogue_generation"
                ),
                model=self.model_name,
                policy=GeminiCallPolicy(max_attempts=1, max_total_wait_seconds=3.0),
                operation=lambda: self._get_client().models.generate_content(
                    model=self.model_name,
                    contents=[self._prompt, self._serialize_request(request)],
                    config=config,
                ),
            )
            parsed = getattr(response, "parsed", None)
            if parsed is not None:
                return DialogueGenerationResult.model_validate(parsed)
            text = getattr(response, "text", None)
            if text:
                return DialogueGenerationResult.model_validate_json(text)
            raise ProviderResponseValidationError(
                "practice dialogue provider 응답 검증에 실패했습니다."
            )
        except ProviderError:
            raise
        except (ValidationError, TypeError, ValueError):
            raise ProviderResponseValidationError(
                "practice dialogue provider 응답 검증에 실패했습니다."
            ) from None
        except Exception:
            raise ProviderError("Gemini practice dialogue 호출에 실패했습니다.") from None

    @staticmethod
    def _serialize_request(request: DialogueGenerationRequest) -> str:
        payload = {
            "role": {
                "name": request.role,
                "instruction": request.plan.role_instruction,
                "persuasion_instruction": request.plan.persuasion_instruction,
            },
            "approved_facts": [
                fact.model_dump(mode="json") for fact in request.approved_facts
            ],
            "dialogue_plan": request.plan.model_dump(mode="json"),
            "current_context": {
                "scenario_id": request.scenario_id,
                "scenario_version": request.scenario_version,
                "turn_id": request.turn_id,
                "user_answer": request.user_answer,
                "evaluation_category": request.evaluation_category,
                "correction_codes": list(request.correction_codes),
            },
        }
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def build_practice_dialogue_provider(
    scenario: ScenarioDefinition,
    *,
    offline_mode: bool = False,
    client: Any | None = None,
) -> PracticeDialogueProvider | None:
    if scenario.grounded_roleplay is None or offline_mode:
        return None
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return None
    return GeminiPracticeDialogueProvider(client=client, api_key=api_key)
