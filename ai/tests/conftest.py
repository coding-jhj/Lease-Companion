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
