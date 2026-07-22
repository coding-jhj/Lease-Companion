"""R/J 결과를 바꾸지 않고 피해 유형 비교표를 결정적으로 구성한다."""

from __future__ import annotations

from collections.abc import Iterable

from lease_companion_ai.schemas.unified import (
    AnalysisRunResult,
    DamagePatternComparison,
    DamagePatternStatus,
    JudgmentResult,
    OfficialSource,
    RuleResult,
    RuleStatus,
)

from .reference_cases import search_reference_cases


def _sources(results: Iterable[RuleResult]) -> tuple[OfficialSource, ...]:
    unique: dict[str, OfficialSource] = {}
    for result in results:
        for source in result.evidence_sources:
            unique.setdefault(source.source_id, source)
    return tuple(unique.values())


def _comparison(
    *,
    pattern_id: str,
    pattern_name: str,
    status: DamagePatternStatus,
    reason: str,
    limitations: str,
    rules: tuple[RuleResult, ...],
    judgment_ids: tuple[str, ...] = (),
) -> DamagePatternComparison:
    return DamagePatternComparison(
        pattern_id=pattern_id,
        pattern_name=pattern_name,
        status=status,
        reason=reason,
        related_rule_ids=tuple(rule.rule_id for rule in rules),
        related_judgment_ids=judgment_ids,
        limitations=limitations,
        official_sources=_sources(rules),
        # 참고 사례는 표시 상태가 실제 확인 대상으로 남은 경우에만 붙이며,
        # 판정·시급도·공식 근거·행동 생성에는 사용하지 않는다.
        reference_cases=(
            search_reference_cases(pattern_id)
            if status is not DamagePatternStatus.NO_SIGNAL_IN_SUBMITTED_DOCS
            else ()
        ),
    )


def build_damage_patterns_from_results(
    rule_results: Iterable[RuleResult],
    judgment_results: Iterable[JudgmentResult] = (),
) -> list[DamagePatternComparison]:
    """저장 실행 식별자 없이 R/J 결과만으로 피해 유형 비교표를 만든다."""

    rules = {item.rule_id: item for item in rule_results}
    judgments = {item.judgment_id: item for item in judgment_results}
    # v1.8 호환 R01~R10 저장 결과에는 외부자료·확인입력 규칙이 없으므로
    # 불완전한 비교표를 추정해 만들지 않는다.
    if any(f"R{index:02d}" not in rules for index in range(1, 25)):
        return []

    owner = rules["R01"]
    owner_status = (
        DamagePatternStatus.RELATED_SIGNAL
        if owner.status is RuleStatus.MISMATCH
        else DamagePatternStatus.NO_SIGNAL_IN_SUBMITTED_DOCS
        if owner.status is RuleStatus.MATCH
        else DamagePatternStatus.CANNOT_ASSESS
    )

    account = rules["R06"]
    account_status = (
        DamagePatternStatus.RELATED_SIGNAL
        if account.status is RuleStatus.MISMATCH
        else DamagePatternStatus.NO_SIGNAL_IN_SUBMITTED_DOCS
        if account.status is RuleStatus.MATCH
        else DamagePatternStatus.CANNOT_ASSESS
    )

    trust = rules["R05"]
    trust_status = (
        DamagePatternStatus.RELATED_SIGNAL
        if trust.status is RuleStatus.CHECK_NEEDED
        else DamagePatternStatus.NO_SIGNAL_IN_SUBMITTED_DOCS
        if trust.status is RuleStatus.NOT_APPLICABLE
        else DamagePatternStatus.CANNOT_ASSESS
    )

    refund_rule = rules["R08"]
    # J10은 반환 시점뿐 아니라 조건의 명확성까지 판정하므로, 확장 분석에서는
    # 피해 유형 표시 상태와 이유에 J10 결과를 우선 사용한다.
    refund = judgments.get("J10", refund_rule)
    deferred_refund_signal = (
        refund.status is RuleStatus.CHECK_NEEDED
        and "신규 임차인" in refund.reason
    )
    refund_status = (
        DamagePatternStatus.NO_SIGNAL_IN_SUBMITTED_DOCS
        if refund.status is RuleStatus.CLEAR
        else DamagePatternStatus.RELATED_SIGNAL
        if refund.status in {RuleStatus.UNCLEAR, RuleStatus.NOT_STATED}
        or deferred_refund_signal
        else DamagePatternStatus.CANNOT_ASSESS
    )

    mortgage = rules["R03"]
    mortgage_reason = (
        "근저당 설정: 관련 확인 신호 발견. 과도한 근저당 여부: 추가 확인 필요. "
        "이유: 비교할 주택가치와 실제 선순위 금액 자료가 부족합니다."
        if mortgage.status is RuleStatus.CHECK_NEEDED
        else mortgage.reason
    )

    return [
        _comparison(
            pattern_id="DP01", pattern_name="소유자 사칭 계약", status=owner_status,
            reason=owner.reason,
            limitations="제출된 계약서와 등기사항증명서의 이름 비교 결과이며 신분증 진위는 판단하지 않습니다.",
            rules=(owner,), judgment_ids=("J01",),
        ),
        _comparison(
            pattern_id="DP02", pattern_name="제3자 계좌 입금", status=account_status,
            reason=account.reason,
            limitations="계약서에 기재된 예금주와 계약 상대의 이름만 비교하며 계좌의 실제 소유·권한은 판단하지 않습니다.",
            rules=(account,), judgment_ids=("J05",),
        ),
        _comparison(
            pattern_id="DP03", pattern_name="보증금 대비 주택가치 확인", status=DamagePatternStatus.CANNOT_ASSESS,
            reason=rules["R20"].reason,
            limitations="공식 실거래가·전세가 외부 데이터가 연결되기 전에는 이른바 깡통전세 여부를 자동 판정하지 않습니다.",
            rules=(rules["R11"], rules["R20"]),
        ),
        _comparison(
            pattern_id="DP04", pattern_name="근저당·선순위 권리", status=(
                DamagePatternStatus.RELATED_SIGNAL
                if mortgage.status is RuleStatus.CHECK_NEEDED
                else DamagePatternStatus.NO_SIGNAL_IN_SUBMITTED_DOCS
                if mortgage.status is RuleStatus.NOT_APPLICABLE
                else DamagePatternStatus.CANNOT_ASSESS
            ),
            reason=mortgage_reason,
            limitations="근저당의 존재나 채권최고액만으로 보증금 회수 가능성 또는 계약 위험을 확정하지 않습니다.",
            rules=(mortgage, rules["R12"]),
        ),
        _comparison(
            pattern_id="DP05", pattern_name="신탁주택 계약 권한", status=trust_status,
            reason=trust.reason,
            limitations="신탁 기재가 없다는 사실만으로 계약 권한이나 향후 권리변동을 보장하지 않습니다.",
            rules=(trust, rules["R17"]),
        ),
        _comparison(
            pattern_id="DP06", pattern_name="선순위 임차보증금", status=DamagePatternStatus.CANNOT_ASSESS,
            reason=rules["R23"].reason,
            limitations="현재 업로드 문서만으로 동일 건물의 전체 선순위 임차보증금을 자동 확인할 수 없습니다.",
            rules=(rules["R23"],),
        ),
        _comparison(
            pattern_id="DP07", pattern_name="계약 후 권리변동", status=DamagePatternStatus.PREVENTIVE_CHECK,
            reason=rules["R10"].reason,
            limitations="계약 이후 발생할 수 있는 근저당 설정·압류·소유권 변경을 현재 문서로 미리 판단하지 않습니다.",
            rules=(rules["R10"], rules["R19"]),
        ),
        _comparison(
            pattern_id="DP08", pattern_name="보증금 반환 조건", status=refund_status,
            reason=refund.reason,
            limitations="계약서 문구의 명확성을 확인하며 실제 반환 이행 여부를 예측하지 않습니다.",
            rules=(refund_rule,), judgment_ids=("J10",),
        ),
    ]


def build_damage_patterns(analysis: AnalysisRunResult) -> list[DamagePatternComparison]:
    return build_damage_patterns_from_results(analysis.results, analysis.judgments)


def attach_damage_patterns(analysis: AnalysisRunResult) -> AnalysisRunResult:
    return analysis.model_copy(update={"damage_patterns": build_damage_patterns(analysis)})
