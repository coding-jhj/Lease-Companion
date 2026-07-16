# frontend/

슬기로운 계약생활의 사용자 화면. **회원·계약 관리를 포함한 모바일 최적화 웹앱**이다. PC 중심이 아니라 모바일 웹앱을 기준으로 설계한다.

> **기술 스택 확정(2026-07-16): React + Vite + TypeScript.** ([`../docs/decisions/2026-07-16-mvp-platform-stack.md`](../docs/decisions/2026-07-16-mvp-platform-stack.md)) 프로젝트 초기화는 이제 가능하며 별도 구현 작업으로 진행한다 — 현재는 폴더 구조와 지시서만 존재한다(미초기화).

## 목적

로그인한 사용자가 **계약 건 단위**로 계약 문서를 관리한다. 사용자 흐름 8단계를 화면으로 제공하고, AI 추출 결과를 사용자가 확인·수정하게 하며, 분석 결과·체크리스트·계약 직후 행동 상태를 계약 건에 저장하고 재조회한다.

## 사용자 흐름 8단계 ↔ 화면 매핑

| 단계 | 흐름 | 담당 페이지 (`src/pages`) |
|------|------|--------------------------|
| 1 | 회원가입·로그인 | `auth` |
| 2 | 계약 대시보드·계약 건 생성 | `dashboard`, `contract-create` |
| 3 | 계약 상황 입력 | `contract-create` |
| 4 | 계약서·등기 등 문서 업로드 | `document-upload` |
| 5 | 추출값 확인·수정 | `extraction-review` |
| 6 | 분석 (상용 LLM 구조화 → 규칙 엔진 → RAG → 상용 LLM 생성, 로컬 7B는 선택적 성능비교 실험) | `analysis-progress` |
| 7 | 판정·원문 증거·공식 근거·질문·행동 리포트 | `result-report` |
| 8 | 체크리스트·계약 직후 행동 관리 | `contract-detail` |

## 하위 구조

```
public/assets/          정적 에셋
src/
  pages/                화면 단위 (책임: pages/README.md)
  features/             흐름 단계별 기능 모듈 (책임: features/README.md)
  components/           common/ layout/ feedback/ 공통 UI
  services/             API 호출
  types/                백엔드 스키마 대응 타입
  hooks/ utils/ styles/
tests/                  components/ features/ pages/
```

각 페이지·feature 디렉터리는 이미 존재하며 `.gitkeep`으로 유지한다. **`.gitkeep`을 삭제하지 않는다.**

## 향후 구현 위치 (초기화 후)

- 화면 컴포넌트 → `src/pages/<page>/`
- 기능 로직·상태·UI → `src/features/<feature>/`
- API 클라이언트 → `src/services`
- 백엔드 스키마 대응 타입 → `src/types` (`docs/api/` 확정 후)
- 테스트 → `tests/`

## 저장하면 안 되는 파일

- 실제 개인정보·계약 문서
- API 키·비밀정보

## 다른 폴더와의 연결

- `backend/` API를 호출하고 스키마 타입을 동기화한다. (`docs/api/`)

## 현재 상태 / TODO

- 폴더 구조·지시서만 존재. 화면 미구현. 프로젝트 미초기화.
- 확정(2026-07-16): **React + Vite + TypeScript**. 인증은 JWT Bearer(토큰 정책 TODO — Backend 기준을 따름).
- **TODO**: 프로젝트 초기화 후 의존성·실행 명령 기록 (구현 작업에서 진행)
- **TODO**: 백엔드 API 확정 후 `src/types` 정의 — mock과 실제 API가 같은 응답 타입 사용, 추출값 확인·수정 화면은 canonical Pydantic 계약(`user_corrected_value`·`verification_status`·3등급 confidence·nullable `page`/`text`)을 따름
- 화면 확인 우선순위 3단계(반드시 확인·확인 권장·일반 확인) 매핑과 접근성 원칙은 [`AGENTS.md`](AGENTS.md) 참조
