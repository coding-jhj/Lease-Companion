"""공식 근거에 한정해 사용자 안내를 생성하고 안전한 fallback을 제공한다."""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Iterable
from pathlib import Path
from types import MappingProxyType

from lease_companion_ai.generation.models import (
    GeneratedGuidanceDraft,
    GenerationMethod,
    GenerationResult,
    GuidanceActionItem,
    JudgmentGuidance,
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
    ContractContext,
    ContractStage,
    GENERATION_PROMPT_VERSION,
    JudgmentResult,
    RuleResult,
    StageGuidance,
    validate_generation_result_for_analysis,
)

PROMPT_NAMES = ("questions", "checklists", "summaries")
logger = logging.getLogger(__name__)


def load_generation_prompts(root: Path | None = None) -> MappingProxyType[str, str]:
    prompt_root = root or Path(__file__).resolve().parents[3] / "prompts"
    prompts = {
        name: (prompt_root / name / f"{GENERATION_PROMPT_VERSION}.txt").read_text(
            encoding="utf-8"
        )
        for name in PROMPT_NAMES
    }
    if any(not prompt.strip() for prompt in prompts.values()):
        raise ValueError("생성 프롬프트는 비어 있을 수 없습니다.")
    for name, prompt in prompts.items():
        expected_header = f"버전: {name}-{GENERATION_PROMPT_VERSION}"
        if prompt.splitlines()[0].strip() != expected_header:
            raise ValueError(f"생성 프롬프트 헤더는 {expected_header}이어야 합니다.")
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

    def generate(
        self, analysis: AnalysisRunResult, contract_context: ContractContext
    ) -> GenerationResult:
        if analysis.contract_id != contract_context.contract_id:
            raise ValueError("분석 결과와 ContractContext의 contract_id가 다릅니다.")
        before = analysis.model_dump(mode="json")
        items = tuple(
            self._generate_rule(result)
            for result in analysis.results
            if result.triggers_actions
        )
        judgment_items = tuple(
            self._generate_judgment(result)
            for result in analysis.judgments
            if result.triggers_actions
        )
        if analysis.model_dump(mode="json") != before:
            raise RuntimeError("생성 단계가 규칙 결과를 변경했습니다.")
        generated = GenerationResult(
            analysis_run_id=analysis.analysis_run_id,
            prompt_version=GENERATION_PROMPT_VERSION,
            items=items,
            judgment_items=judgment_items,
            stage_guidance=self._stage_guidance(analysis, contract_context),
        )
        return validate_generation_result_for_analysis(analysis, generated)

    @staticmethod
    def _stage_guidance(
        analysis: AnalysisRunResult, contract_context: ContractContext
    ) -> StageGuidance:
        judgments = {item.judgment_id: item for item in analysis.judgments}
        after_contract = (
            contract_context.contract_stage is ContractStage.AFTER_CONTRACT
            or contract_context.signed
        )

        before_deposit_questions: tuple[str, ...] = ()
        if not contract_context.deposit_paid and not after_contract:
            before_deposit_questions = GenerationService._unique(
                judgments[judgment_id].question
                for judgment_id in ("J01", "J04", "J05", "J07")
                if judgment_id in judgments
                and judgments[judgment_id].triggers_actions
                and judgments[judgment_id].question
            )

        signing_checklist: tuple[str, ...] = ()
        if not after_contract:
            signing_checklist = GenerationService._unique(
                action
                for judgment_id in ("J02", "J06", "J08", "J09", "J10", "J11", "J12")
                if judgment_id in judgments and judgments[judgment_id].triggers_actions
                for action in judgments[judgment_id].recommended_actions
            )

        post_contract_actions: list[str] = []
        if after_contract:
            post_contract_actions.append(
                "실제 입주 후 전입신고·확정일자 등 권리 확보 절차와 요건을 공식 안내에서 확인하세요."
            )
            if contract_context.balance_payment_date is not None:
                post_contract_actions.append(
                    f"잔금 지급 예정일({contract_context.balance_payment_date.isoformat()})의 "
                    "이체내역과 잔금 지급 전 확인 자료를 보관하세요."
                )
            if contract_context.move_in_date is not None:
                post_contract_actions.append(
                    f"입주 예정일({contract_context.move_in_date.isoformat()})에 실제 인도 상태와 "
                    "열쇠 수령 내용을 기록하세요."
                )

        record_retention = ["계약 관련 대화와 확인 자료를 보관하세요."]
        if after_contract:
            record_retention.append("서명된 계약서 사본을 보관하세요.")
        if contract_context.deposit_paid:
            record_retention.append("계약금 이체내역을 보관하세요.")
        if contract_context.balance_payment_date is not None:
            record_retention.append("잔금 이체내역을 계약 건에 함께 보관하세요.")

        return StageGuidance(
            contract_context=contract_context,
            before_deposit_questions=before_deposit_questions,
            signing_checklist=signing_checklist,
            post_contract_actions=GenerationService._unique(post_contract_actions),
            record_retention=GenerationService._unique(record_retention),
        )

    @staticmethod
    def _unique(values: Iterable[str | None]) -> tuple[str, ...]:
        return tuple(dict.fromkeys(value for value in values if value))

    def _generate_rule(self, result: RuleResult) -> RuleGuidance:
        if not result.evidence_sources:
            return self._safe_fallback(result, "missing_evidence")
        if self._provider is None:
            return self._safe_fallback(result, "provider_unavailable")

        tokenizer = PiiTokenizer()
        request = GenerationRequest(
            prompt_version=GENERATION_PROMPT_VERSION,
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

    def _generate_judgment(self, result: JudgmentResult) -> JudgmentGuidance:
        if not result.evidence_sources:
            return self._safe_judgment_fallback(result, "missing_evidence")
        if self._provider is None:
            return self._safe_judgment_fallback(result, "provider_unavailable")

        tokenizer = PiiTokenizer()
        request = GenerationRequest(
            prompt_version=GENERATION_PROMPT_VERSION,
            rule_id=result.judgment_id,
            rule_name=self._tokenize_required(tokenizer, result.judgment_name),
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
                extra={
                    "judgment_id": result.judgment_id,
                    "reason_codes": ("raw_pii",),
                },
            )
            return self._safe_judgment_fallback(
                result, "pii_tokenization_failed"
            )
        try:
            draft = self._provider.generate(request)
        except ProviderError:
            return self._safe_judgment_fallback(result, "provider_error")

        restored = self._restore_draft(tokenizer, draft)
        guidance = JudgmentGuidance(
            judgment_id=result.judgment_id,
            explanation=restored.explanation,
            questions=restored.questions,
            signing_checklist=restored.signing_checklist,
            post_contract_actions=restored.post_contract_actions,
            signing_checklist_items=self._action_items(
                result.judgment_id, "checklist", restored.signing_checklist
            ),
            post_contract_action_items=self._action_items(
                result.judgment_id, "post_action", restored.post_contract_actions
            ),
            source_ids=restored.source_ids,
            generation_method=GenerationMethod.PROVIDER,
            provider_model=self._provider.model_name,
        )
        try:
            return self._guardrails.enforce_judgment(result, guidance)
        except GuardrailBlocked as exc:
            reason = (
                "invalid_source_id"
                if exc.reasons == ("invalid_source_id",)
                else f"guardrail_blocked:{','.join(exc.reasons)}"
            )
            return self._safe_judgment_fallback(result, reason)

    def _safe_judgment_fallback(
        self, result: JudgmentResult, reason: str
    ) -> JudgmentGuidance:
        fallback = self._judgment_fallback(result, reason)
        try:
            return self._guardrails.enforce_judgment(result, fallback)
        except GuardrailBlocked as exc:
            has_evidence = bool(result.evidence_sources)
            minimal = JudgmentGuidance(
                judgment_id=result.judgment_id,
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
            return self._guardrails.enforce_judgment(result, minimal)

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
    def _judgment_fallback(
        result: JudgmentResult, reason: str
    ) -> JudgmentGuidance:
        has_evidence = bool(result.evidence_sources)
        source_ids = tuple(source.source_id for source in result.evidence_sources)
        questions = (result.question,) if result.question else ()
        signing_checklist = (
            tuple(result.recommended_actions) if has_evidence else ()
        )
        return JudgmentGuidance(
            judgment_id=result.judgment_id,
            explanation=(
                f"{result.judgment_name}: {result.reason} 공식 근거와 함께 확인하십시오."
                if has_evidence
                else f"{result.judgment_name}: 공식 근거 확인이 필요합니다. 관련 내용을 직접 확인하십시오."
            ),
            questions=questions,
            signing_checklist=signing_checklist,
            post_contract_actions=(),
            signing_checklist_items=GenerationService._action_items(
                result.judgment_id, "checklist", signing_checklist
            ),
            source_ids=source_ids,
            generation_method=GenerationMethod.TEMPLATE_FALLBACK,
            fallback_reason=reason,
        )

    @staticmethod
    def _action_items(
        result_id: str, kind: str, texts: tuple[str, ...]
    ) -> tuple[GuidanceActionItem, ...]:
        return tuple(
            GuidanceActionItem(
                item_key=(
                    f"{result_id}:{kind}:"
                    + hashlib.sha256(
                        f"{result_id}|{kind}|{text}".encode("utf-8")
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
