from __future__ import annotations

from pathlib import Path
import pytest

from lease_companion_ai.generation.models import (
    GeneratedGuidanceDraft,
    GenerationMethod,
    JudgmentGuidance,
    RuleGuidance,
)
from lease_companion_ai.generation.service import (
    GenerationService,
    load_generation_prompts,
)
from lease_companion_ai.providers.generation import FakeGenerationProvider
from lease_companion_ai.schemas.unified import (
    AnalysisRunResult,
    ContractContext,
    JudgmentResult,
    OfficialSource,
)

# CWD와 무관하게 repo 루트 기준으로 fixture를 찾는다(다른 테스트와 동일한 앵커).
ROOT = Path(__file__).resolve().parents[3]


def _context(
    *,
    contract_id: int = 1,
    contract_stage: str = "계약금 입금 전",
    deposit_paid: bool = False,
    signed: bool = False,
    move_in_date: str | None = None,
    balance_payment_date: str | None = None,
) -> ContractContext:
    return ContractContext(
        contract_id=contract_id,
        contract_type="전세",
        contract_stage=contract_stage,
        deposit_paid=deposit_paid,
        signed=signed,
        move_in_date=move_in_date,
        balance_payment_date=balance_payment_date,
        is_proxy_contract=False,
    )


def _analysis() -> AnalysisRunResult:
    from lease_companion_ai.schemas.unified import (
        ResultType,
        RuleResult,
        RuleStatus,
        Urgency,
    )

    results = []
    for index in range(1, 11):
        rule_id = f"R{index:02d}"
        active = index in {1, 2}
        status = (
            RuleStatus.CHECK_NEEDED
            if active
            else (
                RuleStatus.CLEAR if index in {8, 9, 10} else RuleStatus.NOT_APPLICABLE
            )
        )
        if index in {1, 2, 6} and not active:
            status = RuleStatus.MATCH
        if index == 7:
            status = RuleStatus.CHECK_NEEDED
            active = True
        source = (
            [
                OfficialSource(
                    source_id="SRC-HTA-LAW",
                    title="법령",
                    institution="국가법령정보센터",
                )
            ]
            if index == 1
            else []
        )
        results.append(
            RuleResult(
                rule_id=rule_id,
                rule_name=f"규칙 {rule_id}",
                result_type=(
                    ResultType.JUDGMENT
                    if index in {1, 2, 6, 8, 9}
                    else ResultType.FACT_FLAG
                ),
                triggers_actions=active,
                status=status,
                urgency=Urgency.BEFORE_CONTRACT if active else Urgency.REFERENCE,
                reason=f"{rule_id} 확인 사유",
                question=f"{rule_id}을 확인했습니까?",
                recommended_actions=[f"{rule_id} 자료를 확인하십시오."],
                evidence_sources=source,
                limitations="제공된 문서 범위",
            )
        )
    return AnalysisRunResult(
        analysis_run_id="RUN-GEN-001",
        input_snapshot_id="SNAP-GEN-001",
        contract_id=1,
        results=results,
    )


def _analysis_with_judgments(*, with_j01_evidence: bool = True) -> AnalysisRunResult:
    analysis = _analysis()
    statuses = {
        "J01": "불일치",
        "J02": "일치",
        "J03": "적용 제외",
        "J04": "적용 제외",
        "J05": "일치",
        "J06": "명확",
        "J07": "일치",
        "J08": "일치",
        "J09": "명확",
        "J10": "명확",
        "J11": "명확",
        "J12": "명확",
    }
    judgments = [
        JudgmentResult(
            judgment_id=judgment_id,
            judgment_name=f"판정 {judgment_id}",
            status=status,
            urgency="즉시 확인" if judgment_id == "J01" else "참고",
            triggers_actions=judgment_id == "J01",
            reason=f"{judgment_id} 확인 사유",
            question=f"{judgment_id}을 확인했습니까?" if judgment_id == "J01" else None,
            recommended_actions=(
                [f"{judgment_id} 자료를 확인하십시오."] if judgment_id == "J01" else []
            ),
            evidence_sources=(
                [
                    OfficialSource(
                        source_id="SRC-J01",
                        title="J01 공식자료",
                        institution="공공기관",
                    )
                ]
                if judgment_id == "J01" and with_j01_evidence
                else []
            ),
            limitations="제공된 문서 범위",
        )
        for judgment_id, status in statuses.items()
    ]
    return AnalysisRunResult.model_validate(
        analysis.model_copy(update={"judgments": judgments}).model_dump()
    )


def test_provider_output_is_grounded_and_rule_results_are_immutable():
    analysis = _analysis()
    before = analysis.model_dump(mode="json")
    provider = FakeGenerationProvider(
        {
            "R01": GeneratedGuidanceDraft(
                explanation="공식 근거에 따라 소유자 정보를 확인하십시오.",
                questions=("등기 소유자와 계약 상대가 같은가요?",),
                signing_checklist=("등기사항증명서의 소유자를 확인하십시오.",),
                source_ids=("SRC-HTA-LAW",),
            )
        }
    )

    generated = GenerationService(provider).generate(analysis, _context())

    assert analysis.model_dump(mode="json") == before
    assert [item.rule_id for item in generated.items] == ["R01", "R02", "R07"]
    assert generated.items[0].generation_method is GenerationMethod.PROVIDER
    assert generated.items[0].provider_model == "fake-generation-v1"
    assert generated.items[0].source_ids == ("SRC-HTA-LAW",)
    action = generated.items[0].signing_checklist_items[0]
    assert action.text == "등기사항증명서의 소유자를 확인하십시오."
    assert action.item_key.startswith("R01:checklist:")
    assert len(action.item_key.rsplit(":", 1)[1]) == 12
    assert [call.rule_id for call in provider.calls] == ["R01"]


def test_missing_evidence_skips_provider_and_does_not_confirm_actions():
    analysis = _analysis()
    provider = FakeGenerationProvider({})

    generated = GenerationService(provider).generate(analysis, _context())
    missing = next(item for item in generated.items if item.rule_id == "R02")

    assert missing.generation_method is GenerationMethod.TEMPLATE_FALLBACK
    assert missing.fallback_reason == "missing_evidence"
    assert missing.source_ids == ()
    assert missing.signing_checklist == ()
    assert missing.post_contract_actions == ()
    assert "공식 근거 확인이 필요" in missing.explanation
    assert [call.rule_id for call in provider.calls] == ["R01"]


def test_provider_failure_returns_structured_fallback():
    analysis = _analysis()
    provider = FakeGenerationProvider({}, failing_rule_ids=frozenset({"R01"}))

    generated = GenerationService(provider).generate(analysis, _context())
    failed = generated.items[0]

    assert failed.generation_method is GenerationMethod.TEMPLATE_FALLBACK
    assert failed.fallback_reason == "provider_error"
    assert failed.source_ids == ("SRC-HTA-LAW",)
    assert failed.signing_checklist == ("R01 자료를 확인하십시오.",)
    assert failed.signing_checklist_items[0].text == "R01 자료를 확인하십시오."
    assert failed.signing_checklist_items[0].item_key.startswith("R01:checklist:")


def test_unknown_provider_source_id_uses_fallback():
    analysis = _analysis()
    provider = FakeGenerationProvider(
        {
            "R01": GeneratedGuidanceDraft(
                explanation="잘못된 근거",
                source_ids=("SRC-NOT-PROVIDED",),
            )
        }
    )

    generated = GenerationService(provider).generate(analysis, _context())

    assert generated.items[0].generation_method is GenerationMethod.TEMPLATE_FALLBACK
    assert generated.items[0].fallback_reason == "invalid_source_id"
    assert generated.items[0].source_ids == ("SRC-HTA-LAW",)
    assert (
        generated.items[0].signing_checklist_items[0].text == "R01 자료를 확인하십시오."
    )


def test_prompts_are_loaded_from_versioned_files():
    analysis = _analysis()
    provider = FakeGenerationProvider(
        {
            "R01": GeneratedGuidanceDraft(
                explanation="근거 확인",
                source_ids=("SRC-HTA-LAW",),
            )
        }
    )

    generated = GenerationService(provider).generate(analysis, _context())

    assert generated.prompt_version == "v2"
    assert provider.calls[0].prompt_version == "v2"
    assert set(provider.calls[0].prompts) == {"questions", "checklists", "summaries"}
    assert all("버전:" in prompt for prompt in provider.calls[0].prompts.values())


def test_prompt_loader_rejects_header_that_does_not_match_prompt_set(
    tmp_path: Path,
):
    for name in ("questions", "checklists", "summaries"):
        directory = tmp_path / name
        directory.mkdir()
        (directory / "v2.txt").write_text(
            f"버전: {name}-v2\n역할: 테스트", encoding="utf-8"
        )
    (tmp_path / "questions" / "v2.txt").write_text(
        "버전: questions-v1\n역할: 잘못된 버전", encoding="utf-8"
    )

    with pytest.raises(ValueError, match="questions-v2"):
        load_generation_prompts(tmp_path)


def test_case001_fixture_can_use_template_fallback_with_contract_context():
    fixture = ROOT / "data/sample/fixtures/case-001/analysis_run_result.json"
    analysis = AnalysisRunResult.model_validate_json(
        fixture.read_text(encoding="utf-8")
    )

    generated = GenerationService().generate(analysis, _context(contract_id=1001))

    assert generated.analysis_run_id == analysis.analysis_run_id
    assert generated.items
    assert all(
        item.generation_method is GenerationMethod.TEMPLATE_FALLBACK
        for item in generated.items
    )


def test_provider_request_is_tokenized_and_output_is_restored_locally():
    analysis = _analysis()
    analysis.results[
        0
    ].reason = (
        "임대인: 홍길동, 주소: 서울특별시 종로구 새싹로 12, 계좌번호: 110-123-456789"
    )
    provider = FakeGenerationProvider(
        {
            "R01": GeneratedGuidanceDraft(
                explanation="임대인 [PERSON_1]의 등기 정보를 확인하십시오.",
                source_ids=("SRC-HTA-LAW",),
            )
        }
    )

    generated = GenerationService(provider).generate(analysis, _context())

    request = provider.calls[0]
    request_text = " ".join(
        [
            request.rule_name,
            request.reason,
            request.limitations,
            *(value for value in request.prompts.values()),
        ]
    )
    assert "홍길동" not in request_text
    assert "서울특별시 종로구 새싹로 12" not in request_text
    assert "110-123-456789" not in request_text
    assert "[PERSON_1]" in request.reason
    assert "[ADDRESS_1]" in request.reason
    assert "[ACCOUNT_1]" in request.reason
    assert generated.items[0].explanation == "임대인 홍길동의 등기 정보를 확인하십시오."
    assert generated.guardrail_passed is True


def test_prohibited_provider_output_is_replaced_with_guarded_fallback(caplog):
    analysis = _analysis()
    analysis.results[0].reason = "임대인: 홍길동 확인 필요"
    provider = FakeGenerationProvider(
        {
            "R01": GeneratedGuidanceDraft(
                explanation="이 계약은 안전합니다.",
                source_ids=("SRC-HTA-LAW",),
            )
        }
    )

    generated = GenerationService(provider).generate(analysis, _context())

    item = generated.items[0]
    assert item.generation_method is GenerationMethod.TEMPLATE_FALLBACK
    assert item.fallback_reason == "guardrail_blocked:prohibited_claim"
    assert "안전합니다" not in item.explanation
    assert "홍길동" not in caplog.text


def test_provider_unavailable_fallback_is_guarded_again():
    analysis = _analysis()
    analysis.results[0].reason = "이 계약은 안전합니다."

    generated = GenerationService().generate(analysis, _context())

    item = generated.items[0]
    assert item.generation_method is GenerationMethod.TEMPLATE_FALLBACK
    assert item.fallback_reason == "guardrail_blocked_fallback:prohibited_claim"
    assert item.explanation == "이 항목은 연결된 공식 근거와 함께 직접 확인하십시오."
    assert item.questions == ()
    assert item.signing_checklist == ()


def test_contract_context_changes_stage_guidance_deterministically():
    fixture = ROOT / "data/sample/fixtures/case-001/analysis_run_result.json"
    analysis = AnalysisRunResult.model_validate_json(
        fixture.read_text(encoding="utf-8")
    )
    before = _context(
        contract_id=1001,
        move_in_date="2026-09-01",
        balance_payment_date="2026-08-30",
    )

    before_result = GenerationService().generate(analysis, before)
    before_guidance = before_result.stage_guidance
    assert before_guidance.contract_context == before
    assert before_guidance.before_deposit_questions
    assert before_guidance.signing_checklist
    assert before_guidance.post_contract_actions == ()
    assert all(
        "계약금 이체내역" not in item for item in before_guidance.record_retention
    )

    after = _context(
        contract_id=1001,
        contract_stage="계약 직후",
        deposit_paid=True,
        signed=True,
        move_in_date="2026-09-01",
        balance_payment_date="2026-08-30",
    )
    after_result = GenerationService().generate(analysis, after)
    after_guidance = after_result.stage_guidance
    assert after_guidance.before_deposit_questions == ()
    assert after_guidance.signing_checklist == ()
    assert any("2026-09-01" in item for item in after_guidance.post_contract_actions)
    assert any("계약금 이체내역" in item for item in after_guidance.record_retention)
    assert before_result.stage_guidance != after_result.stage_guidance


def test_guidance_actions_are_deduplicated_and_assigned_to_the_right_stage():
    service = GenerationService()
    rule_signing = ("등기사항증명서 갑구의 소유자를 확인한다.",)
    rule_post = (
        "계약 후 30일 이내에 임대차 신고를 한다.",
        "계약금은 임대인 명의의 계좌로 송금한다.",
    )
    judgment_signing = ("등기상 소유자와 계약자가 일치하는지 확인한다.",)
    judgment_post = (
        "계약 후 30일 이내에 주택임대차 신고를 완료한다.",
        "주민센터에서 전입신고와 확정일자를 받는다.",
    )
    rule = RuleGuidance(
        rule_id="R01",
        explanation="R01 안내",
        generation_method=GenerationMethod.TEMPLATE_FALLBACK,
        fallback_reason="test",
        signing_checklist=rule_signing,
        post_contract_actions=rule_post,
        signing_checklist_items=service._action_items("R01", "checklist", rule_signing),
        post_contract_action_items=service._action_items(
            "R01", "post_action", rule_post
        ),
    )
    judgment = JudgmentGuidance(
        judgment_id="J01",
        explanation="J01 안내",
        generation_method=GenerationMethod.TEMPLATE_FALLBACK,
        fallback_reason="test",
        signing_checklist=judgment_signing,
        post_contract_actions=judgment_post,
        signing_checklist_items=service._action_items(
            "J01", "checklist", judgment_signing
        ),
        post_contract_action_items=service._action_items(
            "J01", "post_action", judgment_post
        ),
    )

    rules, judgments = service._compact_guidance_actions((rule,), (judgment,))

    assert rules[0].signing_checklist == (
        "최신 등기사항증명서의 소유자와 계약 상대가 일치하는지 확인하고, 다르면 계약 권한 서류를 확인하세요.",
        "입금 전에 계좌 명의와 계약 상대가 일치하는지 확인하세요.",
    )
    assert rules[0].post_contract_actions == (
        "신고 대상 여부를 확인하고, 대상이면 계약 체결일부터 30일 이내에 주택 임대차 계약 신고를 완료한 뒤 처리 결과를 보관하세요.",
    )
    assert judgments[0].signing_checklist == ()
    assert judgments[0].post_contract_actions == (
        "실제 입주 후 전입신고·확정일자 등 권리 확보 절차를 완료하고 처리 결과를 확인하세요.",
    )


def test_generation_rejects_contract_context_for_another_contract():
    with pytest.raises(ValueError, match="contract_id"):
        GenerationService().generate(_analysis(), _context(contract_id=2))


def test_judgment_provider_output_is_grounded_and_analysis_is_immutable():
    analysis = _analysis_with_judgments()
    before = analysis.model_dump(mode="json")
    provider = FakeGenerationProvider(
        {
            "R01": GeneratedGuidanceDraft(
                explanation="R01 공식 근거를 확인하십시오.",
                source_ids=("SRC-HTA-LAW",),
            ),
            "J01": GeneratedGuidanceDraft(
                explanation="J01 공식 근거에 따라 계약 상대를 확인하십시오.",
                questions=("계약 상대와 소유자가 일치합니까?",),
                signing_checklist=("소유자 자료를 대조하십시오.",),
                source_ids=("SRC-J01",),
            ),
        }
    )

    generated = GenerationService(provider).generate(analysis, _context())

    assert analysis.model_dump(mode="json") == before
    assert [item.judgment_id for item in generated.judgment_items] == ["J01"]
    assert generated.judgment_items[0].generation_method is GenerationMethod.PROVIDER
    assert generated.judgment_items[0].source_ids == ("SRC-J01",)
    action = generated.judgment_items[0].signing_checklist_items[0]
    assert action.text == "소유자 자료를 대조하십시오."
    assert action.item_key.startswith("J01:checklist:")
    assert len(action.item_key.rsplit(":", 1)[1]) == 12
    assert [call.rule_id for call in provider.calls] == ["R01", "J01"]


def test_judgment_missing_evidence_uses_safe_fallback_without_actions():
    generated = GenerationService().generate(
        _analysis_with_judgments(with_j01_evidence=False), _context()
    )

    item = generated.judgment_items[0]
    assert item.judgment_id == "J01"
    assert item.generation_method is GenerationMethod.TEMPLATE_FALLBACK
    assert item.fallback_reason == "missing_evidence"
    assert item.source_ids == ()
    assert item.signing_checklist == ()
    assert item.post_contract_actions == ()
    assert "공식 근거 확인이 필요" in item.explanation


def test_prohibited_judgment_output_is_replaced_with_guarded_fallback():
    provider = FakeGenerationProvider(
        {
            "R01": GeneratedGuidanceDraft(
                explanation="R01 공식 근거를 확인하십시오.",
                source_ids=("SRC-HTA-LAW",),
            ),
            "J01": GeneratedGuidanceDraft(
                explanation="이 계약은 안전합니다.",
                source_ids=("SRC-J01",),
            ),
        }
    )

    generated = GenerationService(provider).generate(
        _analysis_with_judgments(), _context()
    )

    item = generated.judgment_items[0]
    assert item.generation_method is GenerationMethod.TEMPLATE_FALLBACK
    assert item.fallback_reason == "guardrail_blocked:prohibited_claim"
    assert "안전합니다" not in item.explanation


def test_judgment_provider_request_is_tokenized_and_restored_locally():
    analysis = _analysis_with_judgments()
    analysis.judgments[
        0
    ].reason = "임대인: 홍길동, 주소: 서울특별시 종로구 새싹로 12 확인 필요"
    provider = FakeGenerationProvider(
        {
            "R01": GeneratedGuidanceDraft(
                explanation="R01 공식 근거를 확인하십시오.",
                source_ids=("SRC-HTA-LAW",),
            ),
            "J01": GeneratedGuidanceDraft(
                explanation="임대인 [PERSON_1]의 주소 [ADDRESS_1]을 확인하십시오.",
                source_ids=("SRC-J01",),
            ),
        }
    )

    generated = GenerationService(provider).generate(analysis, _context())

    request = next(call for call in provider.calls if call.rule_id == "J01")
    assert "홍길동" not in request.reason
    assert "서울특별시 종로구 새싹로 12" not in request.reason
    assert "[PERSON_1]" in request.reason
    assert "[ADDRESS_1]" in request.reason
    restored = generated.judgment_items[0].explanation
    assert "홍길동" in restored
    assert "서울특별시 종로구 새싹로 12" in restored
    assert "[PERSON_1]" not in restored
    assert "[ADDRESS_1]" not in restored


def test_unknown_judgment_provider_source_id_uses_fallback():
    provider = FakeGenerationProvider(
        {
            "R01": GeneratedGuidanceDraft(
                explanation="R01 공식 근거를 확인하십시오.",
                source_ids=("SRC-HTA-LAW",),
            ),
            "J01": GeneratedGuidanceDraft(
                explanation="잘못된 근거입니다.",
                source_ids=("SRC-NOT-PROVIDED",),
            ),
        }
    )

    generated = GenerationService(provider).generate(
        _analysis_with_judgments(), _context()
    )

    item = generated.judgment_items[0]
    assert item.generation_method is GenerationMethod.TEMPLATE_FALLBACK
    assert item.fallback_reason == "invalid_source_id"
    assert item.source_ids == ("SRC-J01",)
