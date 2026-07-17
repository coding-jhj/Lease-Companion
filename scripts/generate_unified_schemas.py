"""통합 Pydantic 모델 → JSON Schema 생성기.

단일 원본은 ai/src/lease_companion_ai/schemas/unified.py 의 Pydantic 모델이다.
이 산출물(data/schemas/generated/)은 Backend·Frontend 참조용이며 손으로 수정하지 않는다.

실행:
    conda run -n lease-py310 python scripts/generate_unified_schemas.py

출력은 결정적(정렬·고정 포맷) — 재실행 시 모델이 안 변했으면 git diff가 없어야 한다.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ai" / "src"))

from lease_companion_ai.schemas.unified import (  # noqa: E402
    SCHEMA_VERSION,
    AnalysisRunResult,
    ContractContext,
    CorrectionRequest,
    DocumentExtraction,
    GenerationResult,
    InputSnapshot,
)

OUTPUT_DIR = ROOT / "data" / "schemas" / "generated"

MODELS = {
    "contract-context": ContractContext,
    "document-extraction": DocumentExtraction,
    "input-snapshot": InputSnapshot,
    "correction-request": CorrectionRequest,
    "analysis-run-result": AnalysisRunResult,
    "generation-result": GenerationResult,
}


def build_schema(name: str, model) -> dict:
    schema = model.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = f"lease-companion/{name}-v{SCHEMA_VERSION}.schema.json"
    schema["x-schema-version"] = SCHEMA_VERSION
    return schema


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, model in MODELS.items():
        path = OUTPUT_DIR / f"{name}.schema.json"
        payload = json.dumps(build_schema(name, model), ensure_ascii=False, indent=2, sort_keys=True)
        path.write_text(payload + "\n", encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
