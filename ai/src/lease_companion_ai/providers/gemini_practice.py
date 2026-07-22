"""Google GenAI SDK 기반 계약 연습 답변 평가 provider와 선택 factory."""

from __future__ import annotations

import json
import os
from typing import Any

from pydantic import ValidationError

from lease_companion_ai.providers.errors import (
    ProviderError,
    ProviderResponseValidationError,
)
from lease_companion_ai.schemas.simulation import (
    PracticeTurnEvaluation,
    ScenarioDefinition,
)
from lease_companion_ai.simulation.models import PracticeAnswerKey
from lease_companion_ai.simulation.provider import (
    PracticeAnswerProvider,
    PracticeEvaluationRequest,
    load_practice_prompt,
)


def _clean_response_schema(node: Any) -> Any:
    if isinstance(node, dict):
        return {
            key: _clean_response_schema(value)
            for key, value in node.items()
            if key not in ("additionalProperties", "title", "default")
        }
    if isinstance(node, list):
        return [_clean_response_schema(item) for item in node]
    return node


_PRACTICE_RESPONSE_SCHEMA = _clean_response_schema(
    PracticeTurnEvaluation.model_json_schema()
)


class GeminiPracticeProvider:
    """사용자 답변 의미만 구조화하고 R/J 판정은 변경하지 않는다."""

    model_name = "gemini-3.5-flash"

    def __init__(
        self,
        *,
        client: Any | None = None,
        api_key: str | None = None,
        prompt: str | None = None,
        timeout_seconds: float = 30.0,
        max_output_tokens: int = 600,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds는 양수여야 합니다.")
        if max_output_tokens <= 0:
            raise ValueError("max_output_tokens는 양수여야 합니다.")
        self._client = client
        self._api_key = api_key
        self._prompt = prompt or load_practice_prompt()
        self._timeout_seconds = timeout_seconds
        self._max_output_tokens = max_output_tokens

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        api_key = (
            self._api_key
            or os.getenv("GEMINI_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
        )
        if not api_key:
            raise ProviderError("Gemini practice provider 설정이 없습니다.")
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
                "Gemini practice provider 초기화에 실패했습니다."
            ) from None
        return self._client

    def classify(
        self, request: PracticeEvaluationRequest
    ) -> PracticeTurnEvaluation:
        try:
            from google.genai import types

            response = self._get_client().models.generate_content(
                model=self.model_name,
                contents=[self._prompt, self._serialize_request(request)],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=_PRACTICE_RESPONSE_SCHEMA,
                    temperature=0,
                    max_output_tokens=self._max_output_tokens,
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
                ),
            )
            parsed = getattr(response, "parsed", None)
            if parsed is not None:
                return PracticeTurnEvaluation.model_validate(parsed)
            text = getattr(response, "text", None)
            if text:
                return PracticeTurnEvaluation.model_validate_json(text)
            raise ProviderResponseValidationError(
                "practice provider 응답 검증에 실패했습니다."
            )
        except TimeoutError:
            raise
        except ProviderResponseValidationError:
            raise
        except ValidationError:
            raise ProviderResponseValidationError(
                "practice provider 응답 검증에 실패했습니다."
            ) from None
        except ProviderError:
            raise
        except Exception:
            raise ProviderError("Gemini practice 호출에 실패했습니다.") from None

    @staticmethod
    def _serialize_request(request: PracticeEvaluationRequest) -> str:
        payload = {
            "prompt_version": request.prompt_version,
            "scenario_id": request.scenario_id,
            "scenario_version": request.scenario_version,
            "turn_id": request.turn_id,
            "prompt": request.prompt,
            "user_answer": request.user_answer,
            "response_time_seconds": request.response_time_seconds,
            "goal_action_id": request.goal_action_id,
            "required_semantics": list(request.required_semantics),
            "partial_semantics": list(request.partial_semantics),
            "not_sufficient": list(request.not_sufficient),
            "allowed_confirmed_action_ids": [request.goal_action_id],
            "allowed_next_states": [
                request.success_next_state,
                request.retry_state,
            ],
            "rule_states": [
                {
                    "rule_id": state.rule_id,
                    "status": state.status.value,
                    "urgency": state.urgency.value,
                }
                for state in request.rule_states
            ],
            "judgment_states": [
                {
                    "judgment_id": state.judgment_id,
                    "status": state.status.value,
                    "urgency": state.urgency.value,
                }
                for state in request.judgment_states
            ],
        }
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)


class FakePracticeProvider:
    """승인 answer key 예시만 재생하는 네트워크 없는 provider."""

    model_name = "fake-practice-answer-key-v1"

    def __init__(
        self,
        scenario: ScenarioDefinition,
        answer_key: PracticeAnswerKey,
    ) -> None:
        if (
            scenario.scenario_id != answer_key.scenario_id
            or scenario.scenario_version != answer_key.scenario_version
        ):
            raise ValueError("시나리오와 정답표가 일치하지 않습니다.")
        self._scenario = scenario
        self._answer_key = answer_key
        self.calls: list[PracticeEvaluationRequest] = []

    def classify(
        self, request: PracticeEvaluationRequest
    ) -> PracticeTurnEvaluation:
        self.calls.append(request)
        if (
            request.scenario_id != self._scenario.scenario_id
            or request.scenario_version != self._scenario.scenario_version
        ):
            raise ProviderError("Fake practice provider 시나리오가 일치하지 않습니다.")
        example = next(
            (
                item
                for item in self._answer_key.evaluation_examples
                if item.turn_id == request.turn_id
                and item.user_input == request.user_answer
            ),
            None,
        )
        if example is None:
            return PracticeTurnEvaluation(
                turn_id=request.turn_id,
                answer_category="needs_review",
                confirmed_action_ids=[],
                next_dialogue_state=request.retry_state,
                fallback_reason="fake_no_matching_example",
                evidence_text=request.user_answer,
            )
        if example.input_context.provider_error == "timeout":
            raise TimeoutError
        fallback_reason = (
            "conflicting_semantics"
            if example.expected_status_id == "needs_review"
            else None
        )
        return PracticeTurnEvaluation(
            turn_id=request.turn_id,
            answer_category=example.expected_status_id,
            confirmed_action_ids=list(example.expected_confirmed_action_ids),
            next_dialogue_state=example.expected_next_turn_id,
            fallback_reason=fallback_reason,
            evidence_text=request.user_answer,
        )


def build_practice_provider(
    scenario: ScenarioDefinition,
    answer_key: PracticeAnswerKey,
    *,
    offline_mode: bool = False,
    client: Any | None = None,
) -> PracticeAnswerProvider | None:
    """키가 있으면 Gemini, 없고 offline이면 Fake, 그 외에는 None."""

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if api_key:
        return GeminiPracticeProvider(client=client, api_key=api_key)
    if offline_mode:
        return FakePracticeProvider(scenario, answer_key)
    return None
