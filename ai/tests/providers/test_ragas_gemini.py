from __future__ import annotations

from types import SimpleNamespace

from lease_companion_ai.providers.ragas_gemini import GeminiRagasLLM


class FakeModels:
    def __init__(self) -> None:
        self.calls = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            text='{"statements":["근거에 따른 응답"]}',
            candidates=[
                SimpleNamespace(
                    finish_reason=SimpleNamespace(name="STOP")
                )
            ],
        )


class FakePrompt:
    def to_string(self) -> str:
        return "RAGAS 평가 prompt"


def test_ragas_gemini_adapter_returns_langchain_llm_result() -> None:
    models = FakeModels()
    adapter = GeminiRagasLLM(
        client=SimpleNamespace(models=models),
        model="gemini-test",
    )

    result = adapter.generate_text(FakePrompt(), temperature=0)

    assert result.generations[0][0].text.startswith("{")
    assert models.calls[0]["model"] == "gemini-test"
    assert models.calls[0]["contents"] == "RAGAS 평가 prompt"
    assert adapter.is_finished(result) is True


def test_ragas_gemini_adapter_groups_requested_generations_for_one_prompt() -> None:
    adapter = GeminiRagasLLM(
        client=SimpleNamespace(models=FakeModels()),
        model="gemini-test",
    )

    result = adapter.generate_text(FakePrompt(), n=3, temperature=0)

    assert len(result.generations) == 1
    assert len(result.generations[0]) == 3
