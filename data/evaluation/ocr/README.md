# OCR 실측 평가 (Gemini VLM)

OCR = 상용 LLM(Gemini 3.5 Flash) VLM 통합 결정([`../../../docs/decisions/2026-07-14-ocr-gemini-integration.md`](../../../docs/decisions/2026-07-14-ocr-gemini-integration.md)) 후, **한국어 계약/등기 문서를 제대로 읽는지** 검증하는 하네스.

## 실행
```bash
# 1) 레포 루트 .env 에 키 (gitignore됨)
#    GEMINI_API_KEY=...
# 2) 테스트 문서(디지털 PDF) 위치: 기본 ~/Downloads, 또는 LEASE_TEST_DOCS 로 지정
python data/evaluation/ocr/ocr_eval.py
```
산출물은 `_output/`(gitignore)에 저장: 리포트·렌더이미지·OCR 원문.

## 설계
디지털 PDF → PyMuPDF 텍스트 = 정답(GT) / 같은 PDF 래스터화(200 DPI) = 스캔 시뮬 / Gemini OCR → 비교.

## 지표 (해석 주의)
- **① CER**: VLM은 마크다운·시각적 읽기순서로 출력해 PyMuPDF(텍스트레이어 순서)와 구조가 달라 **CER이 과대 측정됨. 실제 오류율 아님 — 참고용.**
- **② 핵심필드 충실도** ⭐: 금액·이름·날짜를 **환각 없이 한 글자도 안 틀리고** 읽는지. 계약 앱의 **진짜 지표**.
- **③ 표 인식**: 등기부 갑구/을구 표 구조 보존.

## 1차 결과 (2026-07-14, gemini-3.5-flash, 200 DPI)
| 문서 | 핵심필드 충실도 | 표 | CER(참고) |
|---|---|---|---|
| 모의 등기부(값 채워짐) | **7/7 정확** (환각 0) | 보존 ✅ | 56% |
| 표준계약서(빈양식) | 해당없음 | — | 64% |

→ **결론: Gemini가 한국어 등기부의 금액·이름·날짜·번호를 정확히 읽음(환각 없음), 표 구조 유지.** OCR 방향 검증 통과.

## 남은 검증 (TODO)
- **값이 채워진 표준계약서**로 충실도 재측정(현재 표준계약서는 빈양식이라 충실도 대상 아님) → task 1 "작성본" 필요.
- **열화 버전**(노이즈·저DPI·skew) 스캔 시뮬로 강건성.
- 실제 스캔/사진 문서 확보 시 재측정.
