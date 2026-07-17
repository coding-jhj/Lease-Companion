from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
import threading
import time

import pytest

from lease_companion_ai.extraction import gemini_extractor as gemini


def _contract_fields() -> gemini.ContractFields:
    return gemini.ContractFields(
        contract_type="전세",
        landlord_name="임대인",
        tenant_name="임차인",
        agent_name=None,
        property_address="가상시 안전구 1",
        deposit=100_000_000,
        monthly_rent=None,
        contract_payment=10_000_000,
        balance_payment=90_000_000,
        account_holder="임대인",
        start_date="2026-08-01",
        end_date="2028-07-31",
        move_in_date="2026-08-01",
        deposit_return_condition="명확",
        repair_responsibility="명확",
        rights_change_clause_present=True,
    )


def test_scanned_contract_uses_one_structured_call(monkeypatch):
    calls = []

    class Models:
        def generate_content(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(parsed=_contract_fields(), text=None)

    monkeypatch.setattr(gemini, "_client", lambda: SimpleNamespace(models=Models()))
    result = gemini.extract_scanned_fields(
        b"image-bytes",
        "image/png",
        "contract",
        budget=gemini.ExternalCallBudget(),
    )

    assert result["landlord_name"] == "임대인"
    assert len(calls) == 1
    assert calls[0]["config"].response_schema is gemini.ContractFields
    assert calls[0]["config"].thinking_config.thinking_level.value == "MINIMAL"


def test_external_call_budget_rejects_excess_calls():
    budget = gemini.ExternalCallBudget(maximum=2)
    budget.consume()
    budget.consume()
    with pytest.raises(gemini.GeminiExtractError, match="호출 한도"):
        budget.consume()


def test_vlm_semaphore_caps_concurrency(monkeypatch):
    active = 0
    maximum = 0
    lock = threading.Lock()

    class Models:
        def generate_content(self, **kwargs):
            nonlocal active, maximum
            with lock:
                active += 1
                maximum = max(maximum, active)
            time.sleep(0.02)
            with lock:
                active -= 1
            return SimpleNamespace(parsed=_contract_fields(), text=None)

    monkeypatch.setattr(gemini, "_client", lambda: SimpleNamespace(models=Models()))
    monkeypatch.setattr(gemini, "_VLM_SEMAPHORE", threading.BoundedSemaphore(2))

    with ThreadPoolExecutor(max_workers=5) as pool:
        list(pool.map(lambda _: gemini._generate(["prompt"], gemini.ContractFields), range(5)))

    assert maximum == 2


def test_digital_text_is_deidentified_before_gemini_and_restored(monkeypatch):
    calls = []

    class Models:
        def generate_content(self, **kwargs):
            calls.append(kwargs)
            fields = _contract_fields().model_copy(
                update={
                    "landlord_name": "[PERSON_1]",
                    "property_address": "[ADDRESS_1]",
                }
            )
            return SimpleNamespace(parsed=fields, text=None)

    monkeypatch.setattr(gemini, "_client", lambda: SimpleNamespace(models=Models()))

    result = gemini.extract_contract_fields(
        "임대인: 홍길동\n소 재 지: 서울특별시 종로구 새싹로 12"
    )

    sent_prompt = calls[0]["contents"][0]
    assert "홍길동" not in sent_prompt
    assert "서울특별시 종로구 새싹로 12" not in sent_prompt
    assert "[PERSON_1]" in sent_prompt
    assert "[ADDRESS_1]" in sent_prompt
    assert result["landlord_name"] == "홍길동"
    assert result["property_address"] == "서울특별시 종로구 새싹로 12"


def test_provider_exception_does_not_expose_sdk_message(monkeypatch):
    class Models:
        def generate_content(self, **kwargs):
            raise RuntimeError("SECRET_PROVIDER_DETAIL")

    monkeypatch.setattr(gemini, "_client", lambda: SimpleNamespace(models=Models()))

    with pytest.raises(gemini.GeminiExtractError) as exc_info:
        gemini.extract_contract_fields("임대인: 홍길동")

    assert "SECRET_PROVIDER_DETAIL" not in str(exc_info.value)
