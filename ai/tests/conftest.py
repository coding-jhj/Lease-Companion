import os
from pathlib import Path
import sys


AI_SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(AI_SRC))

# 기본 테스트는 실제 provider 네트워크를 치지 않는다. 명시적인 smoke 플래그가
# 있을 때만 로컬 키를 보존하며, smoke 테스트 자체도 키 존재를 다시 확인한다.
_live_smoke = any(
    os.getenv(flag) == "1"
    for flag in ("RUN_GEMINI_GENERATION_SMOKE", "RUN_GEMINI_PRACTICE_SMOKE")
)
os.environ["COHERE_API_KEY"] = ""
if not _live_smoke:
    for _offline_key in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        os.environ[_offline_key] = ""

# backend/app/core/db.py가 import 시 load_dotenv()를 호출하므로 로컬 .env의 모델
# 오버라이드가 프로세스 전역에 새어든다. load_dotenv(override=False)가 덮어쓰지
# 못하도록 확정 기본 모델을 선점한다. fallback은 각 테스트가 monkeypatch로 지정한다.
for _model_key in (
    "GEMINI_MODEL_PRACTICE",
    "GEMINI_MODEL_CLASSIFICATION",
    "GEMINI_MODEL_EXTRACTION",
    "GEMINI_MODEL_GENERATION",
):
    os.environ[_model_key] = "gemini-3.5-flash"
os.environ["GEMINI_MODEL_PRACTICE_FALLBACK"] = ""
