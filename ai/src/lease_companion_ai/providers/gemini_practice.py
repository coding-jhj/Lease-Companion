"""Google GenAI SDK 기반 계약 연습 답변 평가 provider와 선택 factory."""

from __future__ import annotations

import json
import os
from typing import Any

from pydantic import ValidationError

from lease_companion_ai.providers.errors import (
    ProviderError,
    ProviderResponseValidationError,
    ProviderTemporaryError,
    ProviderTimeoutError,
)
from lease_companion_ai.providers.gemini_gateway import (
    GeminiCallPolicy,
    GeminiGateway,
    gemini_http_options,
    get_gemini_gateway,
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


_OFFLINE_REQUIRED_KEYWORDS: dict[
    tuple[str, str], tuple[tuple[str, ...], ...]
] = {
    ("PRACTICE-DEFERRED-REFUND-001", "TURN-01"): (
        ("신규임차인", "새임차인", "다음임차인", "후임임차인", "새세입자", "다음세입자", "후임세입자"),
        ("보증금", "반환", "돌려받", "돌려주"),
        ("조건", "입주", "계약종료", "계약끝", "끝나"),
    ),
    ("PRACTICE-DEFERRED-REFUND-001", "TURN-02"): (
        ("신규임차인", "새임차인", "다음임차인", "후임임차인", "새세입자", "다음세입자", "후임세입자"),
        ("특약", "문구", "반환조건"),
        ("수정", "고쳐", "삭제", "바꿔", "제거"),
        ("계약종료", "종료일", "계약끝", "만료", "반환"),
    ),
    ("PRACTICE-DEFERRED-REFUND-001", "TURN-03"): (
        ("특약", "반환조건", "문구"),
        ("수정", "고쳐", "삭제", "변경"),
        ("서명하지", "진행하지", "계약하지", "보류", "중단", "안하", "못하"),
    ),
    ("PRACTICE-THIRD-PARTY-PAYMENT-001", "TURN-01"): (
        ("계좌", "입금명의", "예금주", "명의"),
        ("중개사", "공인중개사"),
        ("임대인", "소유자"),
        ("다르", "아니", "불일치", "이유", "확인"),
    ),
    ("PRACTICE-THIRD-PARTY-PAYMENT-001", "TURN-02"): (
        ("중개사", "공인중개사"),
        ("임대인", "소유자"),
        ("관계", "누구", "어떤사이"),
        ("권한", "위임", "대신받"),
        ("서류", "자료", "증명", "위임장"),
    ),
    ("PRACTICE-THIRD-PARTY-PAYMENT-001", "TURN-03"): (
        ("명의", "계좌", "예금주"),
        ("권한", "위임", "수령"),
        ("송금하지", "입금하지", "보내지", "송금보류", "입금보류"),
    ),
    ("PRACTICE-PROXY-AUTHORITY-001", "TURN-01"): (
        ("등기상소유자", "등기소유자", "소유자"),
        ("대리인", "대리계약", "대신계약"),
        ("관계", "대조", "확인", "누구"),
    ),
    ("PRACTICE-PROXY-AUTHORITY-001", "TURN-02"): (
        ("위임장", "인감증명서", "권한서류", "권한자료"),
        ("권한", "위임범위", "대리권"),
        ("계약체결", "계약권한", "서명"),
        ("계약금수령", "수령권한", "돈받", "입금명의"),
    ),
    ("PRACTICE-PROXY-AUTHORITY-001", "TURN-03"): (
        ("대리권", "위임", "권한"),
        ("서명하지", "계약하지", "서명보류", "계약보류"),
        ("송금하지", "입금하지", "보내지", "송금보류", "입금보류"),
    ),
}

_OFFLINE_BLOCKING_KEYWORDS = (
    "그대로두",
    "나중에확인",
    "일단서명",
    "먼저서명",
    "일단송금",
    "먼저송금",
    "일단입금",
    "먼저입금",
    "송금하겠습니다",
    "입금하겠습니다",
    "보내겠습니다",
    "진행하겠습니다",
)


def _normalize_offline_answer(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())


def _matches_required_offline_intent(request: PracticeEvaluationRequest) -> bool:
    groups = _OFFLINE_REQUIRED_KEYWORDS.get((request.scenario_id, request.turn_id))
    if groups is None:
        return False
    answer = _normalize_offline_answer(request.user_answer)
    if any(keyword in answer for keyword in _OFFLINE_BLOCKING_KEYWORDS):
        return False
    return all(
        any(_normalize_offline_answer(keyword) in answer for keyword in group)
        for group in groups
    )


class GeminiPracticeProvider:
    """사용자 답변 의미만 구조화하고 R/J 판정은 변경하지 않는다."""

    model_name = "gemini-3.5-flash"

    def __init__(
        self,
        *,
        client: Any | None = None,
        gateway: GeminiGateway | None = None,
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
        self.model_name = os.getenv("GEMINI_MODEL_PRACTICE", type(self).model_name)
        # 확인되지 않은 모델 ID를 기본값으로 두지 않는다(설계 원칙). 검증된 2차
        # 모델이 있으면 GEMINI_MODEL_PRACTICE_FALLBACK로 주입한다. 빈 값이면 fallback 없음.
        self.fallback_model_name = os.getenv(
            "GEMINI_MODEL_PRACTICE_FALLBACK", ""
        ).strip()
        self._gateway = gateway or get_gemini_gateway()
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

            self._client = genai.Client(
                api_key=api_key,
                http_options=gemini_http_options(int(self._timeout_seconds * 1_000)),
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

            config = types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=_PRACTICE_RESPONSE_SCHEMA,
                temperature=0,
                max_output_tokens=self._max_output_tokens,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            )
            try:
                response = self._call_model(self.model_name, request, config)
            except (ProviderTemporaryError, ProviderTimeoutError):
                if (
                    not self.fallback_model_name
                    or self.fallback_model_name == self.model_name
                ):
                    raise
                response = self._call_model(
                    self.fallback_model_name,
                    request,
                    config,
                    task="practice_classification_fallback",
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

    def _call_model(
        self,
        model: str,
        request: PracticeEvaluationRequest,
        config: Any,
        *,
        task: str = "practice_classification",
    ) -> Any:
        return self._gateway.call(
            task=task,
            model=model,
            # 설계표: 연습 답변 분류 = 최대 2회 / 총 3초. 일시 503·timeout을 1회 재시도.
            policy=GeminiCallPolicy(max_attempts=2, max_total_wait_seconds=3.0),
            operation=lambda: self._get_client().models.generate_content(
                model=model,
                contents=[self._prompt, self._serialize_request(request)],
                config=config,
            ),
        )

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
    """승인 예시와 제한된 필수 의미를 판별하는 네트워크 없는 provider."""

    model_name = "fake-practice-answer-key-v2"

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
            if _matches_required_offline_intent(request):
                return PracticeTurnEvaluation(
                    turn_id=request.turn_id,
                    answer_category="appropriate_check",
                    confirmed_action_ids=[request.goal_action_id],
                    next_dialogue_state=request.success_next_state,
                    fallback_reason=None,
                    evidence_text=request.user_answer,
                )
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
