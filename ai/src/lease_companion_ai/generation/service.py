"""공식 근거에 한정해 사용자 안내를 생성하고 안전한 fallback을 제공한다."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from types import MappingProxyType

from lease_companion_ai.generation.models import (
    GeneratedGuidanceDraft,
    GenerationMethod,
    GenerationResult,
    GuidanceActionItem,
    RuleGuidance,
)
from lease_companion_ai.guardrails.pii import PiiTokenizer, contains_raw_pii
from lease_companion_ai.guardrails.service import GuardrailBlocked, GuardrailService
from lease_companion_ai.providers.errors import ProviderError
from lease_companion_ai.providers.generation import (
    GenerationEvidence,
    GenerationProvider,
    GenerationRequest,
)
from lease_companion_ai.schemas.unified import (
    AnalysisRunResult,
    RuleResult,
    validate_generation_result_for_analysis,
)

PROMPT_VERSION = "v1"
PROMPT_NAMES = ("questions", "checklists", "summaries")
logger = logging.getLogger(__name__)


def load_generation_prompts(root: Path | None = None) -> MappingProxyType[str, str]:
    prompt_root = root or Path(__file__).resolve().parents[3] / "prompts"
    prompts = {
        name: (prompt_root / name / f"{PROMPT_VERSION}.txt").read_text(
            encoding="utf-8"
        )
        for name in PROMPT_NAMES
    }
    if any(not prompt.strip() for prompt in prompts.values()):
        raise ValueError("생성 프롬프트는 비어 있을 수 없습니다.")
    return MappingProxyType(prompts)


class GenerationService:
    def __init__(
        self,
        provider: GenerationProvider | None = None,
        *,
        prompts: MappingProxyType[str, str] | None = None,
        guardrails: GuardrailService | None = None,
    ) -> None:
        self._provider = provider
        self._prompts = prompts or load_generation_prompts()
        self._guardrails = guardrails or GuardrailService()

    def generate(self, analysis: AnalysisRunResult) -> GenerationResult:
        before = analysis.model_dump(mode="json")
        items = tuple(
            self._generate_rule(result)
            for result in analysis.results
            if result.triggers_actions
        )
        if analysis.model_dump(mode="json") != before:
            raise RuntimeError("생성 단계가 규칙 결과를 변경했습니다.")
        generated = GenerationResult(
            analysis_run_id=analysis.analysis_run_id, items=items
        )
        return validate_generation_result_for_analysis(analysis, generated)

    def _generate_rule(self, result: RuleResult) -> RuleGuidance:
        if not result.evidence_sources:
            return self._safe_fallback(result, "missing_evidence")
        if self._provider is None:
            return self._safe_fallback(result, "provider_unavailable")

        tokenizer = PiiTokenizer()
        request = GenerationRequest(
            rule_id=result.rule_id,
            rule_name=self._tokenize_required(tokenizer, result.rule_name),
            status=result.status.value,
            urgency=result.urgency.value,
            reason=self._tokenize_required(tokenizer, result.reason),
            limitations=self._tokenize_required(tokenizer, result.limitations),
            evidence=tuple(
                GenerationEvidence(
                    source_id=source.source_id,
                    title=self._tokenize_required(tokenizer, source.title),
                    institution=self._tokenize_required(tokenizer, source.institution),
                    summary=tokenizer.tokenize(source.summary),
                    source_url=tokenizer.tokenize(source.source_url),
                )
                for source in result.evidence_sources
            ),
            prompts=MappingProxyType(
                {
                    name: self._tokenize_required(tokenizer, prompt)
                    for name, prompt in self._prompts.items()
                }
            ),
        )
        if self._request_contains_raw_pii(request):
            logger.warning(
                "generation_pii_gate_blocked",
                extra={"rule_id": result.rule_id, "reason_codes": ("raw_pii",)},
            )
            return self._safe_fallback(result, "pii_tokenization_failed")
        try:
            draft = self._provider.generate(request)
        except ProviderError:
            return self._safe_fallback(result, "provider_error")

        restored = self._restore_draft(tokenizer, draft)
        guidance = RuleGuidance(
            rule_id=result.rule_id,
            explanation=restored.explanation,
            questions=restored.questions,
            signing_checklist=restored.signing_checklist,
            post_contract_actions=restored.post_contract_actions,
            signing_checklist_items=self._action_items(
                result.rule_id, "checklist", restored.signing_checklist
            ),
            post_contract_action_items=self._action_items(
                result.rule_id, "post_action", restored.post_contract_actions
            ),
            source_ids=restored.source_ids,
            generation_method=GenerationMethod.PROVIDER,
            provider_model=self._provider.model_name,
        )
        try:
            return self._guardrails.enforce(result, guidance)
        except GuardrailBlocked as exc:
            reason = (
                "invalid_source_id"
                if exc.reasons == ("invalid_source_id",)
                else f"guardrail_blocked:{','.join(exc.reasons)}"
            )
            return self._safe_fallback(result, reason)

    def _safe_fallback(self, result: RuleResult, reason: str) -> RuleGuidance:
        fallback = self._fallback(result, reason)
        try:
            return self._guardrails.enforce(result, fallback)
        except GuardrailBlocked as exc:
            has_evidence = bool(result.evidence_sources)
            minimal = RuleGuidance(
                rule_id=result.rule_id,
                explanation=(
                    "이 항목은 연결된 공식 근거와 함께 직접 확인하십시오."
                    if has_evidence
                    else "이 항목은 공식 근거 확인이 필요합니다. 직접 확인하십시오."
                ),
                source_ids=tuple(
                    source.source_id for source in result.evidence_sources
                ),
                generation_method=GenerationMethod.TEMPLATE_FALLBACK,
                fallback_reason=(
                    "guardrail_blocked_fallback:" + ",".join(exc.reasons)
                ),
            )
            return self._guardrails.enforce(result, minimal)

    @staticmethod
    def _fallback(result: RuleResult, reason: str) -> RuleGuidance:
        has_evidence = bool(result.evidence_sources)
        source_ids = tuple(source.source_id for source in result.evidence_sources)
        questions = (result.question,) if result.question else ()
        signing_checklist = tuple(result.recommended_actions) if has_evidence else ()
        return RuleGuidance(
            rule_id=result.rule_id,
            explanation=(
                f"{result.rule_name}: {result.reason} 공식 근거와 함께 확인하십시오."
                if has_evidence
                else f"{result.rule_name}: 공식 근거 확인이 필요합니다. 관련 내용을 직접 확인하십시오."
            ),
            questions=questions,
            signing_checklist=signing_checklist,
            post_contract_actions=(),
            signing_checklist_items=GenerationService._action_items(
                result.rule_id, "checklist", signing_checklist
            ),
            source_ids=source_ids,
            generation_method=GenerationMethod.TEMPLATE_FALLBACK,
            fallback_reason=reason,
        )

    @staticmethod
    def _action_items(
        rule_id: str, kind: str, texts: tuple[str, ...]
    ) -> tuple[GuidanceActionItem, ...]:
        return tuple(
            GuidanceActionItem(
                item_key=(
                    f"{rule_id}:{kind}:"
                    + hashlib.sha256(
                        f"{rule_id}|{kind}|{text}".encode("utf-8")
                    ).hexdigest()[:12]
                ),
                text=text,
            )
            for text in texts
        )

    @staticmethod
    def _tokenize_required(tokenizer: PiiTokenizer, value: str) -> str:
        tokenized = tokenizer.tokenize(value)
        if tokenized is None:
            raise TypeError("필수 생성 입력은 null일 수 없습니다.")
        return tokenized

    @staticmethod
    def _restore_draft(
        tokenizer: PiiTokenizer, draft: GeneratedGuidanceDraft
    ) -> GeneratedGuidanceDraft:
        return GeneratedGuidanceDraft(
            explanation=GenerationService._restore_required(
                tokenizer, draft.explanation
            ),
            questions=tuple(
                GenerationService._restore_required(tokenizer, value)
                for value in draft.questions
            ),
            signing_checklist=tuple(
                GenerationService._restore_required(tokenizer, value)
                for value in draft.signing_checklist
            ),
            post_contract_actions=tuple(
                GenerationService._restore_required(tokenizer, value)
                for value in draft.post_contract_actions
            ),
            source_ids=draft.source_ids,
        )

    @staticmethod
    def _restore_required(tokenizer: PiiTokenizer, value: str) -> str:
        restored = tokenizer.restore(value)
        if restored is None:
            raise TypeError("필수 생성 출력은 null일 수 없습니다.")
        return restored

    @staticmethod
    def _request_contains_raw_pii(request: GenerationRequest) -> bool:
        values = [
            request.rule_name,
            request.reason,
            request.limitations,
            *request.prompts.values(),
        ]
        for evidence in request.evidence:
            values.extend(
                value
                for value in (
                    evidence.title,
                    evidence.institution,
                    evidence.summary,
                    evidence.source_url,
                )
                if value is not None
            )
        return any(contains_raw_pii(value) for value in values)
