from pathlib import Path
import sys


AI_SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(AI_SRC))
