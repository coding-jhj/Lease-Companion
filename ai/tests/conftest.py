import os
from pathlib import Path
import sys


AI_SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(AI_SRC))

# 테스트는 실제 provider 네트워크를 치지 않는다. 로컬 .env에 키가 있어도
# 라이브 호출이 새지 않도록 오프라인으로 강제한다(backend/tests/conftest.py와 동일).
for _offline_key in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "COHERE_API_KEY"):
    os.environ[_offline_key] = ""
