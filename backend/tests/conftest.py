import os
from pathlib import Path
import sys


# 테스트는 외부 LLM 호출 없이 결정적으로 실행한다. backend/.env에 실제 키가 있어도
# load_dotenv(override=False)가 덮어쓰지 못하도록 빈 값으로 선점해 오프라인 폴백을 강제한다.
# (없으면 분류·생성이 실제 Gemini를 호출해 과금·비결정 실패가 발생한다.)
for _offline_key in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "COHERE_API_KEY"):
    os.environ[_offline_key] = ""
os.environ["PRACTICE_MEDIA_ENABLED"] = "false"

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ai" / "src"))
sys.path.insert(0, str(ROOT / "backend"))
