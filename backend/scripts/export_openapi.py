"""OpenAPI 스키마를 docs/api/openapi.json으로 내보낸다. 실행: backend/ 에서 `python scripts/export_openapi.py`"""

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("JWT_SECRET", "export-only-secret-32-bytes-minimum!")

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND.parent / "ai" / "src"))

from app.main import app  # noqa: E402

OUT = BACKEND.parent / "docs" / "api" / "openapi.json"


def main() -> None:
    spec = app.openapi()
    OUT.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"내보냄: {OUT} (경로 {len(spec['paths'])}개)")


if __name__ == "__main__":
    main()
