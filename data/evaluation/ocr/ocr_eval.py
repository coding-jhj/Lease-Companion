"""Gemini VLM OCR 실측 하네스 — 한국어 계약/등기 문서.

검증 3목표:
  ① 텍스트 정확도(CER) — 단, VLM은 마크다운·시각적 읽기순서로 출력해 PyMuPDF(텍스트레이어 순서)와
     구조가 달라 CER이 과대 측정됨. 실제 오류율 아님. 참고용.
  ② 핵심필드 충실도 — 금액·이름·날짜를 환각 없이 정확히 읽는지 (계약 앱의 진짜 지표).
  ③ 표 인식 — 등기부 갑구/을구 표 구조 보존.

설계: 디지털 PDF → PyMuPDF 텍스트 = 정답(GT) / 같은 PDF 래스터화 = 스캔 시뮬 / Gemini OCR → 비교.

실행:
  1) 레포 루트 `.env`에 GEMINI_API_KEY=... (gitignore됨)
  2) 테스트 문서 경로: 기본 ~/Downloads, 또는 환경변수 LEASE_TEST_DOCS 로 지정
  3) python data/evaluation/ocr/ocr_eval.py
키 없으면: 래스터화·GT·필드체크 준비만 하고 OCR은 건너뜀.
산출물은 `_output/`(gitignore)에 저장.
"""
import os, sys, builtins, re, time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
OUT_DIR = Path(__file__).resolve().parent / "_output"
OUT_DIR.mkdir(exist_ok=True)

_OUT = open(OUT_DIR / "ocr_eval_report.txt", "w", encoding="utf-8")
def log(*a): builtins.print(*a); builtins.print(*a, file=_OUT); _OUT.flush()

import fitz  # PyMuPDF
from rapidfuzz.distance import Levenshtein

# ── 설정 ──────────────────────────────────────────────
MODEL = "gemini-3.5-flash"   # 선정표 확정 모델(I/O 2026 GA). models.list()엔 안 떠도 generateContent 사용 가능.
DPI = 200                    # 스캔 시뮬 해상도
DOCS_DIR = Path(os.environ.get("LEASE_TEST_DOCS", str(Path.home() / "Downloads")))
# 대상: 모의 등기부(값이 채워짐 → 충실도·표 검증) + 표준계약서(빈양식 → 텍스트/레이아웃)
DOCS = {
    "모의등기부": DOCS_DIR / "모의 등기부 등본 양식 (1).pdf",
    "표준계약서": DOCS_DIR / "주택임대차 표준계약서.pdf",
}
# 모의 등기부에 실제로 박힌 핵심 값 — OCR이 '한 글자도 안 틀리고' 읽는지 (환각 체크)
FAITHFULNESS = {
    "모의등기부": [
        "김가상",              # 소유자
        "180,000,000",         # 근저당 채권최고액
        "210,000,000",         # 근저당권변경 후 채권최고액
        "80,000,000",          # 전세금
        "35,000,000",          # 가압류 청구금액
        "2024년 8월 12일",      # 근저당 접수일
        "1111-2026-000001",    # 고유번호
    ],
}

OCR_PROMPT = (
    "이 문서 이미지의 모든 텍스트를 있는 그대로 추출하라.\n"
    "규칙:\n"
    "- 보이는 텍스트만. 없는 내용 추가·추측·요약 금지.\n"
    "- 숫자·금액·날짜·이름·번호는 이미지에 보이는 문자 그대로 옮겨라. "
    "단위 변환·정규화·교정 금지 (예: '삼억원'을 '3억'으로 바꾸지 말 것, 콤마·원 표기 유지).\n"
    "- 읽기 어려운 부분은 [판독불가]로 표기.\n"
    "- 표는 행·열 구조를 유지해 마크다운 표로 출력.\n"
    "- 원문에 나온 순서대로."
)


def normalize(t: str) -> str:
    """비교용: 공백 전부 제거(읽기순서·포맷 차이 노이즈 완화)."""
    return re.sub(r"\s+", "", t or "")


def cer(gt: str, ocr: str) -> float:
    g, o = normalize(gt), normalize(ocr)
    if not g:
        return 0.0
    return Levenshtein.distance(g, o) / len(g)


def gt_text(pdf: Path) -> str:
    with fitz.open(pdf) as d:
        return "\n".join(p.get_text("text") for p in d)


def render_pages(pdf: Path) -> list[bytes]:
    with fitz.open(pdf) as d:
        return [p.get_pixmap(dpi=DPI).tobytes("png") for p in d]


def gemini_ocr(images: list[bytes], client) -> str:
    """페이지별 OCR 후 합침. 503/과부하는 백오프 재시도."""
    from google.genai import types, errors
    out = []
    for idx, img in enumerate(images):
        for attempt in range(5):
            try:
                resp = client.models.generate_content(
                    model=MODEL,
                    contents=[OCR_PROMPT, types.Part.from_bytes(data=img, mime_type="image/png")],
                )
                out.append(resp.text or "")
                break
            except errors.ServerError:
                if attempt == 4:
                    raise
                wait = 5 * (attempt + 1)
                log(f"     (p{idx+1} 503 재시도 {attempt+1}/4, {wait}s 대기)")
                time.sleep(wait)
    return "\n".join(out)


def _load_env():
    envf = REPO_ROOT / ".env"
    if not envf.exists():
        return
    for line in envf.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main():
    _load_env()
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    client = None
    if key:
        from google import genai
        client = genai.Client(api_key=key)
        log(f"[키 확인됨] 모델={MODEL}, DPI={DPI}\n")
    else:
        log("[키 없음] 래스터화·GT·필드체크 준비만. OCR/CER은 GEMINI_API_KEY 설정 후 재실행.\n")

    for name, pdf in DOCS.items():
        if not pdf.exists():
            log(f"### {name}: 파일 없음 {pdf}"); continue
        gt = gt_text(pdf)
        images = render_pages(pdf)
        log(f"### {name}  ({len(images)}쪽, GT {len(gt.strip())}자)")
        for i, img in enumerate(images):
            (OUT_DIR / f"img_{name}_p{i+1}.png").write_bytes(img)

        if not client:
            log("  (OCR 건너뜀 — 키 필요)\n"); continue

        ocr = gemini_ocr(images, client)
        (OUT_DIR / f"ocr_{name}.txt").write_text(ocr, encoding="utf-8")
        log(f"  ① CER(공백무시, 참고용) = {cer(gt, ocr)*100:.2f}%  ※ VLM 포맷차이로 과대측정")

        if name in FAITHFULNESS:
            log("  ② 핵심필드 충실도 (환각 체크):")
            ocr_n = normalize(ocr)
            hit = sum(normalize(v) in ocr_n for v in FAITHFULNESS[name])
            for val in FAITHFULNESS[name]:
                log(f"     {'✅' if normalize(val) in ocr_n else '❌'} {val!r}")
            log(f"     → {hit}/{len(FAITHFULNESS[name])} 정확")
        if name == "모의등기부":
            tbl = all(k in ocr for k in ("갑구", "을구", "근저당권", "순위번호"))
            log(f"  ③ 표 구조 키워드 보존: {'✅' if tbl else '⚠️ 일부 누락'}")
        log("")

    log(f"산출물: {OUT_DIR}")


if __name__ == "__main__":
    main()
