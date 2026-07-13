# frontend/

슬기로운 계약생활의 사용자 화면.

> **기술 스택 미확정.** 프레임워크 코드·`package.json`·설정을 임의로 생성하지 않는다. 현재는 폴더 구조와 지시서만 존재한다.

## 목적

사용자 흐름 6단계를 화면으로 제공하고, AI 추출 결과를 사용자가 확인·수정하게 한다.

## 담당 화면

- 계약 단계 선택
- 계약서·특약 업로드
- AI 추출 정보 확인·수정
- 확인 필요 항목
- 임대인·공인중개사 대상 질문 카드
- 서명 전 체크리스트
- 계약 직후 권리 확보 행동
- 분석 결과 요약

## 하위 구조

```
public/assets/          정적 에셋
src/
  pages/                화면 단위
  features/             흐름 단계별 기능 모듈
    contract-stage/ document-upload/ extraction-review/
    verification-items/ question-cards/ signing-checklist/
    post-contract-actions/ result-report/
  components/           common/ layout/ feedback/
  services/             API 호출
  types/                백엔드 스키마 대응 타입
  hooks/ utils/ styles/
tests/                  components/ features/ pages/
```

## 저장해야 하는 파일

- (스택 확정 후) 화면·컴포넌트·API 클라이언트·타입·테스트 코드
- 정적 에셋(`public/assets`)

## 저장하면 안 되는 파일

- 실제 개인정보·계약 문서
- API 키·비밀정보

## 다른 폴더와의 연결

- `backend/` API를 호출하고 스키마 타입을 동기화한다. (`docs/api/`)

## 현재 상태 / TODO

- 폴더 구조·지시서만 존재. 화면 미구현.
- TODO: 프론트엔드 프레임워크 확정
- TODO: 확정 후 프로젝트 초기화·의존성·실행 명령 기록
- TODO: 백엔드 API 확정 후 `src/types` 정의
