# 피해 유형 비교와 유사 참고 사례 경계

- 상태: 확정
- 일자: 2026-07-21

## 결정

R01~R24와 J01~J12의 판정은 그대로 유지하고, 화면용 `DamagePatternComparison`이 이를 DP01~DP08 피해 유형 관점으로 결정적으로 묶는다. 이 비교 상태는 `RuleStatus`·`urgency`를 대체하거나 변경하지 않는다.

표시 상태는 `관련 확인 신호 있음`·`제출 자료에서 관련 신호 미확인`·`자료 부족으로 확인 불가`·`예방 확인 필요` 네 가지다. `미확인`은 반드시 제출 자료 범위를 함께 표시하며 안전·사기 부재를 뜻하지 않는다.

공식자료는 `official_sources`로 직접 근거에 사용한다. 유사 사례는 `reference_cases`로 분리하며 판정·시급도·핵심 행동의 근거로 사용하지 않는다. 검증된 사례가 없거나 해당 DP 상태가 `제출 자료에서 관련 신호 미확인`이면 빈 목록을 유지하고 사례를 생성하지 않는다.

2026-07-22부터 외부 API 호출 없이 `data/reference-cases/verified_reference_cases.json`의 검증된 공개 메타데이터를 결정적으로 검색한다. HUG의 피해 유형 안내는 공공기관의 예방용 유형 설명으로, 한국부동산원·LH 임대차분쟁조정위원회 자료는 공개된 익명 조정사례로 구분한다. 어느 쪽도 현재 계약의 법적 결론이나 동일 피해 발생을 입증하지 않는다.

## 구현

- canonical 모델: `ai/src/lease_companion_ai/schemas/unified.py`
- 결정적 매핑: `ai/src/lease_companion_ai/risk_patterns/service.py`
- 로컬 사례 검색: `ai/src/lease_companion_ai/risk_patterns/reference_cases.py`
- 검증 사례 메타데이터: `data/reference-cases/verified_reference_cases.json`
- 사용자 화면: `frontend/src/features/damage-patterns/`
- 기존 v1.8·v1.9 저장 결과는 `damage_patterns=[]` 기본값으로 읽는다.

## 제한

근저당 존재·채권최고액만으로 과도 여부나 보증금 회수 가능성을 판정하지 않는다. 근저당 설정이 문서에서 확인되면 DP04는 `관련 확인 신호 있음`으로 표시하되, 이유에서 `근저당 설정 사실`과 `과도성 추가 확인`을 분리한다. 공식 실거래가·전세가와 검증된 기준이 연결되기 전에는 과도 여부를 확정하지 않는다.

현재 사례 검색은 DP01~DP08 식별자 기반 로컬 매핑이다. 전문 의미 검색, 최신 사례 자동 수집, 법원 판례 검색은 포함하지 않는다. 출처 URL·요약·검증 범위는 데이터 검증 스크립트가 검사하며, 원문 전체나 개인정보는 저장하지 않는다.
