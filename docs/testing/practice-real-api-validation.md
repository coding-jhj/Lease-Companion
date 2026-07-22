# 계약 연습 검증 실행 방법

이 문서는 사용자가 계약 연습 화면을 직접 확인하기 위한 실행 방법입니다.

## 가장 쉬운 실행 방법

### 1. Docker Desktop을 켭니다

Docker Desktop이 실행된 상태여야 합니다.

### 2. PowerShell에서 명령 하나를 실행합니다

```powershell
Set-Location C:\Lease-Companion
pwsh -File .\scripts\start-dev.ps1 -PracticeValidation
```

이 명령이 다음 작업을 자동으로 처리합니다.

1. PostgreSQL 실행
2. `backend/.env`가 없으면 로컬 예시 설정 생성
3. Gemini 키와 Frontend MSW 비활성화
4. 계약 연습용 Fake provider 활성화
5. DB migration 적용
6. FastAPI Backend 실행
7. Vite Frontend 실행
8. 서버 준비 상태 확인
9. 기본 브라우저에서 `http://127.0.0.1:5173/signup` 열기

별도의 Gemini API 키는 필요하지 않으며 외부 모델 비용도 발생하지 않습니다.

### 3. 브라우저에서 검증합니다

1. 테스트용 계정으로 회원가입합니다.
2. 로그인합니다.
3. `내 계약` 화면에서 `가상 계약 대화 연습`을 선택합니다.
4. 아래 시나리오 3개가 모두 보이는지 확인합니다.

| 시나리오 | 화면 제목 |
|---|---|
| S1 | 후임 임차인 조건부 보증금 반환 |
| S2 | 공인중개사 명의 계좌로 가계약금 송금 요구 |
| S3 | 대리인 권한 자료 없는 계약 요구 |

각 시나리오에서 다음 순서로 확인합니다.

1. 계약 상황과 특약 확인
2. `대화 연습 시작` 선택
3. 상대방 말에 답변
4. 3개 대화 TURN 진행
5. 최종 행동 선택
6. 결과 복기 화면 확인
7. 새로고침 후 같은 결과가 유지되는지 확인

답변은 정답 문장을 그대로 복사할 필요가 없습니다. 현재 TURN의 핵심 확인 대상과 행동을 자신의 문장으로 말하면 로컬 Fake provider가 시나리오별 필수 의미를 판별합니다. 무관하거나 “나중에 확인하고 먼저 송금·서명하겠다”처럼 상충하는 답변은 다음 TURN으로 진행되지 않습니다.

## 실행 종료

서버를 실행한 PowerShell에서 `Ctrl+C`를 누릅니다.

Backend와 Frontend가 종료됩니다. PostgreSQL Docker 컨테이너는 다음 실행을 위해 유지됩니다.

## 자동 E2E도 실행하려면

수동 화면 확인 중 새 PowerShell을 하나 열고 다음 명령을 실행합니다.

```powershell
Set-Location C:\Lease-Companion\frontend
npm run test:e2e:practice:real
```

자동 E2E는 다음 조합 9개를 실행합니다.

- 시나리오 3개
- 모바일 320×720
- 모바일 360×800
- PC 1440×900

검증 범위는 회원가입·로그인, 시나리오 선택, 미응답 재시도, 3개 TURN, 세션 새로고침 복원, 최종 행동, 결과 저장·재조회입니다.

## 실행되지 않을 때만 확인할 내용

### Docker 오류

Docker Desktop이 완전히 실행됐는지 확인한 뒤 같은 명령을 다시 실행합니다.

### 8000 또는 5173 포트 사용 중

기존 Backend 또는 Frontend 개발 서버를 직접 종료한 뒤 다시 실행합니다. 스크립트는 사용자가 실행 중인 프로세스를 임의로 종료하지 않습니다.

### Python 또는 npm 오류

프로젝트 의존성이 설치되지 않은 환경입니다. 저장소 루트와 `frontend`에서 각각 의존성을 설치한 뒤 다시 실행합니다.

```powershell
Set-Location C:\Lease-Companion
python -m pip install -e .\ai
python -m pip install -e .\backend
Set-Location frontend
npm ci
npx playwright install chromium
```

## 현재 검증 상태

- Practice Frontend 단위·통합 테스트: `94 passed`
- MSW 전용 브라우저 E2E: `9 passed`
- Production build: 성공
- 실제 API 전용 E2E 파일: `frontend/e2e/practice-flow.spec.ts`
- 로컬 자유 답변 판별: 세 시나리오 9개 TURN 지원
- 실제 Gemini 네트워크 호출: 실행하지 않음
