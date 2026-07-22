"""공식 근거에 한정해 사용자 안내를 생성하고 안전한 fallback을 제공한다."""

from __future__ import annotations

import hashlib
import logging
import re
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

_CANONICAL_CLARITY_JUDGMENTS = MappingProxyType(
    {
        "R08": "J10",
        "R09": "J11",
    }
)

_CANONICAL_ACTIONS: tuple[tuple[re.Pattern[str], str, str, str], ...] = (
    (
        re.compile(r"임대차(?:계약)?신고"),
        "lease-report",
        "post_action",
        "신고 대상 여부를 확인하고, 대상이면 계약 체결일부터 30일 이내에 주택 임대차 계약 신고를 완료한 뒤 처리 결과를 보관하세요.",
    ),
    (
        re.compile(r"전입신고|확정일자"),
        "move-in-protection",
        "post_action",
        "실제 입주 후 전입신고·확정일자 등 권리 확보 절차를 완료하고 처리 결과를 확인하세요.",
    ),
    (
        re.compile(
            r"갑구.*소유자|소유자.*갑구|등기상소유자|소유자와계약자|소유자와계약상대|계약권한"
        ),
        "ownership-authority",
        "checklist",
        "최신 등기사항증명서의 소유자와 계약 상대가 일치하는지 확인하고, 다르면 계약 권한 서류를 확인하세요.",
    ),
    (
        re.compile(
            r"최신.*등기|등기사항증명서.*발급|갑구와을구|갑구.*을구|소유권제한|권리제한"
        ),
        "registry-rights",
        "checklist",
        "계약·잔금 직전 최신 등기사항증명서를 발급받아 갑구·을구의 소유권과 권리제한을 확인하세요.",
    ),
    (
        re.compile(r"선순위.*(?:근저당|권리|채권|금액)|근저당.*선순위"),
        "senior-claims",
        "checklist",
        "선순위 권리의 종류와 채권최고액·실채무액을 확인하고 관련 자료를 보관하세요.",
    ),
    (
        re.compile(r"국세|지방세|납세증명|완납증명"),
        "tax-arrears",
        "checklist",
        "계약 전에 적법한 절차로 임대인의 국세·지방세 관련 자료를 확인하고 보관하세요.",
    ),
    (
        re.compile(r"예금주|계좌명의|임대인명의의계좌"),
        "account-holder",
        "checklist",
        "입금 전에 계좌 명의와 계약 상대가 일치하는지 확인하세요.",
    ),
    (
        re.compile(r"계약서주소.*등기|등기상주소|목적물주소"),
        "property-address",
        "checklist",
        "계약서의 목적물 주소와 등기사항증명서의 주소가 일치하는지 확인하세요.",
    ),
    (
        re.compile(r"실거래|시세|전세가"),
        "market-price",
        "checklist",
        "공식 실거래 자료에서 동일·유사 주택의 가격을 확인하고 기준일과 비교 조건을 기록하세요.",
    ),
    (
        re.compile(r"중개대상물.*(?:확인|설명)|확인.?설명서"),
        "broker-disclosure",
        "checklist",
        "서명 전에 중개대상물 확인·설명서의 내용을 확인하고 사본을 교부받으세요.",
    ),
)


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


def rule_results_requiring_guidance(
    analysis: AnalysisRunResult,
) -> tuple[RuleResult, ...]:
    """canonical J 안내가 대체하지 않는 활성 R 결과만 반환한다."""

    available_judgments = {result.judgment_id for result in analysis.judgments}
    return tuple(
        result
        for result in analysis.results
        if result.triggers_actions
        and _CANONICAL_CLARITY_JUDGMENTS.get(result.rule_id)
        not in available_judgments
    )


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
            for result in rule_results_requiring_guidance(analysis)
        )
        judgment_items = tuple(
            self._generate_judgment(result)
            for result in analysis.judgments
            if result.triggers_actions
        )
        if analysis.model_dump(mode="json") != before:
            raise RuntimeError("생성 단계가 규칙 결과를 변경했습니다.")
        items, judgment_items = self._compact_guidance_actions(items, judgment_items)
        generated = GenerationResult(
            analysis_run_id=analysis.analysis_run_id,
            prompt_version=GENERATION_PROMPT_VERSION,
            items=items,
            judgment_items=judgment_items,
            stage_guidance=self._guardrails.enforce_stage(
                self._stage_guidance(analysis, contract_context)
            ),
        )
        return validate_generation_result_for_analysis(analysis, generated)

    @staticmethod
    def _normalize_action(text: str, fallback_kind: str) -> tuple[str, str, str]:
        trimmed = text.strip()
        compact = re.sub(r"\s+", "", trimmed)
        for pattern, identity, kind, canonical_text in _CANONICAL_ACTIONS:
            if pattern.search(compact):
                return identity, kind, canonical_text
        return compact, fallback_kind, trimmed

    @classmethod
    def _compact_guidance_actions(
        cls,
        items: tuple[RuleGuidance, ...],
        judgment_items: tuple[JudgmentGuidance, ...],
    ) -> tuple[tuple[RuleGuidance, ...], tuple[JudgmentGuidance, ...]]:
        """의미가 같은 행동을 한 번만 유지하고 잘못 생성된 실행 단계를 바로잡는다."""
        seen: dict[str, set[str]] = {"checklist": set(), "post_action": set()}

        def compact(guidance: RuleGuidance | JudgmentGuidance):
            result_id = (
                guidance.rule_id
                if isinstance(guidance, RuleGuidance)
                else guidance.judgment_id
            )
            collected: dict[str, list[str]] = {"checklist": [], "post_action": []}
            for fallback_kind, texts in (
                ("checklist", guidance.signing_checklist),
                ("post_action", guidance.post_contract_actions),
            ):
                for text in texts:
                    identity, kind, normalized_text = cls._normalize_action(
                        text, fallback_kind
                    )
                    if identity in seen[kind]:
                        continue
                    seen[kind].add(identity)
                    collected[kind].append(normalized_text)
            signing = tuple(collected["checklist"])
            post_actions = tuple(collected["post_action"])
            return guidance.model_copy(
                update={
                    "signing_checklist": signing,
                    "post_contract_actions": post_actions,
                    "signing_checklist_items": cls._action_items(
                        result_id, "checklist", signing
                    ),
                    "post_contract_action_items": cls._action_items(
                        result_id, "post_action", post_actions
                    ),
                }
            )

        compacted_rules = tuple(compact(item) for item in items)
        compacted_judgments = tuple(compact(item) for item in judgment_items)
        return compacted_rules, compacted_judgments

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
            before_contract_actions=(
                "등기사항증명서의 소유자와 계약 상대가 일치하는지 확인하세요.",
                "대리계약이면 위임장·인감증명서 등 계약 권한 자료를 확인하세요.",
                "공식 실거래 자료에서 동일·유사 주택의 가격과 보증금을 비교하세요.",
                "최신 등기사항증명서에서 근저당·압류·가압류·신탁 기재를 확인하세요.",
                "다가구주택이면 선순위 임차보증금을 확인할 자료를 요청하세요.",
                "보증기관 공식 채널에서 반환보증 가입 요건과 신청 기한을 확인하세요.",
            ),
            during_contract_actions=(
                "보증금 반환 시점과 조건을 계약서에 구체적으로 기재해 달라고 요청하세요.",
                "신규 임차인 입주를 보증금 반환 조건으로 삼는 문구는 삭제 또는 수정을 요청하세요.",
                "잔금 지급 다음 날까지 새로운 권리 설정을 제한하는 특약을 협의해 기재하세요.",
                "반환보증 가입에 필요한 임대인의 서류 제출·확인 협조 내용을 특약으로 협의하세요.",
                "보증 가입이 불가능한 경우의 계약 처리와 지급금 반환 조건을 서면으로 협의하세요.",
                "입금 계좌가 임대인 본인 명의인지 확인하세요.",
                "공인중개사의 서명과 등록번호를 확인하세요.",
            ),
            closing_day_actions=(
                "잔금 송금 직전에 최신 등기사항증명서를 다시 발급해 권리변동을 확인하세요.",
                "계약 당시 없던 근저당·압류·소유권 변경 기재가 생겼는지 확인하세요.",
                "확인된 임대인 명의 계좌로 송금하고 이체내역과 영수증을 보관하세요.",
                "주택 인도 상태와 열쇠 수령 내용을 기록하세요.",
                "실제 입주 후 전입신고·확정일자 등 권리 확보 절차를 진행하세요.",
            ),
            after_contract_actions=(
                "보증기관의 심사를 거쳐 반환보증 가입 결과를 확인하고 자료를 보관하세요.",
                "계약서·등기사항증명서·송금증·중개대상물 확인설명서를 함께 보관하세요.",
                "필요한 시점에 최신 등기사항증명서를 다시 확인해 권리변동을 살펴보세요.",
                "계약 종료 전에 보증금 반환 일정과 대응 절차를 공식 안내에서 확인하세요.",
            ),
        )

    @staticmethod
    def _request_templates(result_id: str) -> tuple[str, ...]:
        templates = {
            "R06": ("입금 계좌를 임대인 본인 명의 계좌로 변경하고 변경 내용을 계약서에 반영해 주세요.",),
            "J05": ("입금 계좌를 임대인 본인 명의 계좌로 변경하고 변경 내용을 계약서에 반영해 주세요.",),
            "R08": ("보증금은 신규 임차인 입주와 관계없이 계약 종료 시 반환하도록 문구를 명확히 수정해 주세요.",),
            "J10": ("보증금은 신규 임차인 입주와 관계없이 계약 종료 시 반환하도록 문구를 명확히 수정해 주세요.",),
            "R10": ("잔금 지급 다음 날까지 근저당 등 새로운 권리를 설정하지 않는다는 특약을 추가해 주세요.",),
            "R19": ("잔금 지급 다음 날까지 근저당 등 새로운 권리를 설정하지 않는다는 특약을 추가해 주세요.",),
            "R15": ("반환보증 가입에 필요한 서류 제출과 확인 절차에 협조한다는 특약을 추가해 주세요.",),
            "J12": ("본문과 특약이 다르게 해석되지 않도록 충돌하는 조건을 하나의 문구로 정리해 주세요.",),
        }
        return templates.get(result_id, ())

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
            request_templates=self._unique(
                (*restored.request_templates, *self._request_templates(result.rule_id))
            ),
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
                    "이 항목은 연결된 공식 근거와 함께 직접 확인해 주세요."
                    if has_evidence
                    else "이 항목은 공식 근거 확인이 필요합니다. 직접 확인해 주세요."
                ),
                source_ids=tuple(
                    source.source_id for source in result.evidence_sources
                ),
                generation_method=GenerationMethod.TEMPLATE_FALLBACK,
                fallback_reason=("guardrail_blocked_fallback:" + ",".join(exc.reasons)),
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
            return self._safe_judgment_fallback(result, "pii_tokenization_failed")
        try:
            draft = self._provider.generate(request)
        except ProviderError:
            return self._safe_judgment_fallback(result, "provider_error")

        restored = self._restore_draft(tokenizer, draft)
        guidance = JudgmentGuidance(
            judgment_id=result.judgment_id,
            explanation=restored.explanation,
            questions=restored.questions,
            request_templates=self._unique(
                (*restored.request_templates, *self._request_templates(result.judgment_id))
            ),
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
                    "이 항목은 연결된 공식 근거와 함께 직접 확인해 주세요."
                    if has_evidence
                    else "이 항목은 공식 근거 확인이 필요합니다. 직접 확인해 주세요."
                ),
                source_ids=tuple(
                    source.source_id for source in result.evidence_sources
                ),
                generation_method=GenerationMethod.TEMPLATE_FALLBACK,
                fallback_reason=("guardrail_blocked_fallback:" + ",".join(exc.reasons)),
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
                f"{result.rule_name}: {result.reason} 공식 근거와 함께 확인해 주세요."
                if has_evidence
                else f"{result.rule_name}: 공식 근거 확인이 필요합니다. 관련 내용을 직접 확인해 주세요."
            ),
            questions=questions,
            request_templates=GenerationService._request_templates(result.rule_id),
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
    def _judgment_fallback(result: JudgmentResult, reason: str) -> JudgmentGuidance:
        has_evidence = bool(result.evidence_sources)
        source_ids = tuple(source.source_id for source in result.evidence_sources)
        questions = (result.question,) if result.question else ()
        signing_checklist = tuple(result.recommended_actions) if has_evidence else ()
        return JudgmentGuidance(
            judgment_id=result.judgment_id,
            explanation=(
                f"{result.judgment_name}: {result.reason} 공식 근거와 함께 확인해 주세요."
                if has_evidence
                else f"{result.judgment_name}: 공식 근거 확인이 필요합니다. 관련 내용을 직접 확인해 주세요."
            ),
            questions=questions,
            request_templates=GenerationService._request_templates(result.judgment_id),
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
            request_templates=tuple(
                GenerationService._restore_required(tokenizer, value)
                for value in draft.request_templates
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
