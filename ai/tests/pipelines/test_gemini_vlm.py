from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
import json
import threading
import time

import pytest

from lease_companion_ai.extraction import gemini_extractor as gemini
from lease_companion_ai.providers.gemini_gateway import GeminiGateway


@pytest.fixture(autouse=True)
def _gateway_without_real_wait(monkeypatch):
    gateway = GeminiGateway(sleep=lambda _seconds: None, jitter=lambda: 0.0)
    monkeypatch.setattr(gemini, "get_gemini_gateway", lambda: gateway)


class RecordingGateway:
    def __init__(self) -> None:
        self.calls = []

    def call(self, **kwargs):
        self.calls.append(kwargs)
        return kwargs["operation"]()


def _contract_fields() -> gemini.ContractFields:
    return gemini.ContractFields(
        contract_type="전세",
        landlord_name="임대인",
        tenant_name="임차인",
        agent_name=None,
        property_address="가상시 안전구 1",
        building_use="아파트",
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
    assert result["building_use"] == "아파트"
    assert len(calls) == 1
    # response_schema는 Gemini가 거부하는 키를 제거한 정리된 스키마(dict)로 전달된다.
    assert calls[0]["config"].response_schema["properties"]["contract_type"]
    assert "additionalProperties" not in json.dumps(calls[0]["config"].response_schema)
    assert calls[0]["config"].thinking_config.thinking_level.value == "MINIMAL"


def test_extraction_routes_transport_through_gateway(monkeypatch):
    gateway = RecordingGateway()

    class Models:
        def generate_content(self, **kwargs):
            return SimpleNamespace(parsed=_contract_fields(), text=None)

    monkeypatch.setattr(gemini, "_client", lambda: SimpleNamespace(models=Models()))
    monkeypatch.setattr(gemini, "get_gemini_gateway", lambda: gateway, raising=False)

    gemini._generate(["prompt"], gemini.ContractFields)

    assert len(gateway.calls) == 1
    assert gateway.calls[0]["task"] == "document_extraction"


def test_transient_server_error_is_retried_then_succeeds(monkeypatch):
    # 스캔 VLM 구조화의 일시 503은 즉시 실패가 아니라 재시도로 흡수돼야 한다.
    from google.genai import errors

    attempts = []

    class Models:
        def generate_content(self, **kwargs):
            attempts.append(1)
            if len(attempts) < 3:
                raise errors.ServerError(503, {"error": {"message": "unavailable"}})
            return SimpleNamespace(parsed=_contract_fields(), text=None)

    monkeypatch.setattr(gemini, "_client", lambda: SimpleNamespace(models=Models()))

    result = gemini._generate(["prompt"], gemini.ContractFields)

    assert result["landlord_name"] == "임대인"
    assert len(attempts) == 3  # 503 두 번 후 세 번째 성공


def test_client_timeout_is_retried_then_succeeds(monkeypatch):
    # 응답 지연으로 클라이언트가 끊기면(서버 499) httpx.TimeoutException이 나는데,
    # 이는 일시 장애이므로 503과 동일하게 재시도해야 한다.
    import httpx

    attempts = []

    class Models:
        def generate_content(self, **kwargs):
            attempts.append(1)
            if len(attempts) < 3:
                raise httpx.ReadTimeout("read timed out")
            return SimpleNamespace(parsed=_contract_fields(), text=None)

    monkeypatch.setattr(gemini, "_client", lambda: SimpleNamespace(models=Models()))

    result = gemini._generate(["prompt"], gemini.ContractFields)

    assert result["landlord_name"] == "임대인"
    assert len(attempts) == 3


def test_falls_back_to_secondary_model_when_primary_overloaded(monkeypatch):
    # 주 모델이 과부하(503)로 재시도 소진되면 대체 모델로 폴백해 성공해야 한다.
    from google.genai import errors

    models_seen = []

    class Models:
        def generate_content(self, **kwargs):
            models_seen.append(kwargs["model"])
            if kwargs["model"] == gemini._MODEL:
                raise errors.ServerError(503, {"error": {"message": "high demand"}})
            return SimpleNamespace(parsed=_contract_fields(), text=None)

    monkeypatch.setattr(gemini, "_client", lambda: SimpleNamespace(models=Models()))

    result = gemini._generate(["prompt"], gemini.ContractFields)

    assert result["landlord_name"] == "임대인"
    assert models_seen.count(gemini._MODEL) == gemini._MAX_STRUCTURE_ATTEMPTS  # 주모델 소진
    assert gemini._FALLBACK_MODEL in models_seen  # 대체 모델로 폴백


def test_raises_when_both_primary_and_fallback_overloaded(monkeypatch):
    from google.genai import errors

    class Models:
        def generate_content(self, **kwargs):
            raise errors.ServerError(503, {"error": {"message": "high demand"}})

    monkeypatch.setattr(gemini, "_client", lambda: SimpleNamespace(models=Models()))

    with pytest.raises(gemini.GeminiExtractError):
        gemini._generate(["prompt"], gemini.ContractFields)


def test_client_api_error_is_not_retried(monkeypatch):
    # 4xx·쿼터(APIError)는 재시도 의미가 없으므로 한 번에 실패해야 한다.
    from google.genai import errors

    attempts = []

    class Models:
        def generate_content(self, **kwargs):
            attempts.append(1)
            raise errors.APIError(400, {"error": {"message": "bad request"}})

    monkeypatch.setattr(gemini, "_client", lambda: SimpleNamespace(models=Models()))

    with pytest.raises(gemini.GeminiExtractError):
        gemini._generate(["prompt"], gemini.ContractFields)

    assert len(attempts) == 1


def test_registry_response_schema_has_no_additional_properties(monkeypatch):
    # RegistryFields.owner_shares는 dict[str,str] → JSON schema에 additionalProperties가 생긴다.
    # Gemini response_schema는 이를 거부(400)하므로, config에 그 키가 남으면 안 된다.
    captured = {}

    class Models:
        def generate_content(self, **kwargs):
            captured["config"] = kwargs["config"]
            fields = gemini.RegistryFields(
                owner_names=["박성우"], is_joint_ownership=False, property_address=None,
                issue_date=None, mortgage_present=None, seizure_present=None,
                provisional_seizure_present=None, trust_present=None, owner_shares=None,
                ground_right_present=None,
            )
            return SimpleNamespace(parsed=fields, text=None)

    monkeypatch.setattr(gemini, "_client", lambda: SimpleNamespace(models=Models()))

    gemini.extract_registry_fields("등기 텍스트")

    schema_json = json.dumps(captured["config"].response_schema)
    assert "additionalProperties" not in schema_json


def test_external_call_budget_rejects_excess_calls():
    budget = gemini.ExternalCallBudget(maximum=2)
    budget.consume()
    budget.consume()
    with pytest.raises(gemini.GeminiExtractError, match="호출 한도"):
        budget.consume()


def test_gateway_caps_vlm_concurrency_to_one(monkeypatch):
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

    assert maximum == 1


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
