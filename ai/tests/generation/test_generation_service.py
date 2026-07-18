from __future__ import annotations

from lease_companion_ai.generation.models import (
    GeneratedGuidanceDraft,
    GenerationMethod,
)
from lease_companion_ai.generation.service import GenerationService
from lease_companion_ai.providers.generation import FakeGenerationProvider
from lease_companion_ai.schemas.unified import AnalysisRunResult, OfficialSource


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
        status = RuleStatus.CHECK_NEEDED if active else (
            RuleStatus.CLEAR if index in {8, 9, 10} else RuleStatus.NOT_APPLICABLE
        )
        if index in {1, 2, 6} and not active:
            status = RuleStatus.MATCH
        if index == 7:
            status = RuleStatus.CHECK_NEEDED
            active = True
        source = (
            [OfficialSource(source_id="SRC-HTA-LAW", title="법령", institution="국가법령정보센터")]
            if index == 1
            else []
        )
        results.append(
            RuleResult(
                rule_id=rule_id,
                rule_name=f"규칙 {rule_id}",
                result_type=(ResultType.JUDGMENT if index in {1, 2, 6, 8, 9} else ResultType.FACT_FLAG),
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

    generated = GenerationService(provider).generate(analysis)

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

    generated = GenerationService(provider).generate(analysis)
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

    generated = GenerationService(provider).generate(analysis)
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

    generated = GenerationService(provider).generate(analysis)

    assert generated.items[0].generation_method is GenerationMethod.TEMPLATE_FALLBACK
    assert generated.items[0].fallback_reason == "invalid_source_id"
    assert generated.items[0].source_ids == ("SRC-HTA-LAW",)
    assert generated.items[0].signing_checklist_items[0].text == "R01 자료를 확인하십시오."


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

    GenerationService(provider).generate(analysis)

    assert set(provider.calls[0].prompts) == {"questions", "checklists", "summaries"}
    assert all("버전:" in prompt for prompt in provider.calls[0].prompts.values())


def test_case001_fixture_can_use_template_fallback_without_schema_changes():
    from pathlib import Path

    fixture = Path("data/sample/fixtures/case-001/analysis_run_result.json")
    analysis = AnalysisRunResult.model_validate_json(fixture.read_text(encoding="utf-8"))

    generated = GenerationService().generate(analysis)

    assert generated.analysis_run_id == analysis.analysis_run_id
    assert generated.items
    assert all(
        item.generation_method is GenerationMethod.TEMPLATE_FALLBACK
        for item in generated.items
    )


def test_provider_request_is_tokenized_and_output_is_restored_locally():
    analysis = _analysis()
    analysis.results[0].reason = (
        "임대인: 홍길동, 주소: 서울특별시 종로구 새싹로 12, "
        "계좌번호: 110-123-456789"
    )
    provider = FakeGenerationProvider(
        {
            "R01": GeneratedGuidanceDraft(
                explanation="임대인 [PERSON_1]의 등기 정보를 확인하십시오.",
                source_ids=("SRC-HTA-LAW",),
            )
        }
    )

    generated = GenerationService(provider).generate(analysis)

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

    generated = GenerationService(provider).generate(analysis)

    item = generated.items[0]
    assert item.generation_method is GenerationMethod.TEMPLATE_FALLBACK
    assert item.fallback_reason == "guardrail_blocked:prohibited_claim"
    assert "안전합니다" not in item.explanation
    assert "홍길동" not in caplog.text


def test_provider_unavailable_fallback_is_guarded_again():
    analysis = _analysis()
    analysis.results[0].reason = "이 계약은 안전합니다."

    generated = GenerationService().generate(analysis)

    item = generated.items[0]
    assert item.generation_method is GenerationMethod.TEMPLATE_FALLBACK
    assert item.fallback_reason == "guardrail_blocked_fallback:prohibited_claim"
    assert item.explanation == "이 항목은 연결된 공식 근거와 함께 직접 확인하십시오."
    assert item.questions == ()
    assert item.signing_checklist == ()
