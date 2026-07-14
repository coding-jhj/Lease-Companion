# OCR 방식 변경 — PaddleOCR-VL 자체호스팅 → 상용 LLM(Gemini) VLM 통합

- **날짜**: 2026-07-14
- **상태**: 확정 (기존 선정표의 "OCR = PaddleOCR-VL-1.6 확정"을 대체)

## 배경 / 문제
- 선정표(2026-07-14)는 OCR을 **PaddleOCR-VL-1.6**(PaddlePaddle 프레임워크, 자체호스팅)로 확정했으나, **설치 난이도**가 높음: PaddlePaddle GPU 휠이 최신 GPU(Blackwell)·Windows·Python 3.13 조합을 따라오지 못함. 팀 판단 "어렵다".
- 별도 OCR 컴포넌트(모델 다운로드·GPU 서빙·버전관리) 유지 부담.

## 선택지
- **A. 전용 OCR API** (Upstage Document Parse $0.01/page · Naver CLOVA 무료 5천건/월): 한국어 최강, 설치 0. 단 컴포넌트 1개 추가.
- **B. 상용 LLM(Gemini) VLM 통합**: 이미 구조화에 확정된 Gemini 3.5 Flash로 이미지→텍스트·구조를 OCR+구조화 **한 번에**. 컴포넌트 감소.
- **C. PaddleOCR-VL 유지**: 설치 난이도 지속.

## 결정
**B 채택.** OCR을 별도 단계로 두지 않고 **Gemini 3.5 Flash(VLM)** 가 문서 이미지에서 직접 텍스트·필드를 인식·구조화한다.
- **디지털 PDF는 그대로 PyMuPDF** 직접 추출(텍스트 레이어 있으면 OCR 불필요 — 비용·정확도 우위 유지).
- 스캔·이미지 문서만 Gemini VLM 경로.
- PaddleOCR-VL-1.6은 **(선택) 성능비교 실험용**으로만 남기고 크리티컬 패스에서 제거.

## 근거
- 추가 의존성 0 (이미 스택에 있음), 설치 문제 없음(HTTP+키).
- 한국어·표·폼 레이아웃을 VLM이 함께 처리.
- 컴포넌트 1개 감소(OCR→구조화 통합).
- 2026 업계 추세: 단일 VLM(문서→마크다운/JSON)이 검출→인식→후처리 파이프라인보다 유리.

## 리스크 / 후속 (반드시 검증)
1. **PII 외부 전송**: 원문 이미지(성명·주민번호·계좌)가 **비식별 전에** Google로 나감. 멘토 피드백 "PII 로컬 한정 재검토"와 상충 가능. (전용 OCR API도 동일 문제.)
   - **결정(2026-07-14)**: **데모 단계에서는 수용**(a안). 비식별 파이프라인은 텍스트 이후 단계(구조화·생성·RAG)에만 적용. **프로덕션 전 재검토 필수** — 이미지 마스킹 or 로컬 OCR 경량 유지 등.
2. **원문 증거 위치**: 리포트 7단계 "원문 증거"에 좌표(bbox)가 필요하면 VLM은 약함 → 텍스트 인용 기반으로 설계하거나 별도 위치 정보 확보.
3. **OCR 충실도**: VLM이 금액·숫자를 "보정"/환각할 위험(계약 금액 오독은 치명). → 추출 eval로 CER·필드정확도 측정 후 확정.
4. **비용·지연**: 페이지당 토큰 비용·응답시간 측정.

## 영향받는 폴더·문서
- `AGENTS.md`, `ai/AGENTS.md` (OCR 확정 문구·미정기술 표·파이프라인) — 갱신함.
- 후속 갱신 대상(문맥 언급): `README.md`, `docs/architecture/ai-pipeline.md`, `docs/ai/extraction-design.md`, `docs/ai/model-routing.md`, `ai/src/.../ingestion/`·`routing/` README. (건드리는 김에 순차 갱신.)
- 선정표: OCR 행 "PaddleOCR-VL-1.6 확정" → "Gemini VLM 통합" + PaddleOCR는 선택 실험.
