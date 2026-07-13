# data/

슬기로운 계약생활의 데이터 계층. 입력·분석 기준·결과 데이터를 관리한다.

## 목적

샘플 문서, 문서 필드 스키마, 문서 비교 규칙, 공식 RAG 자료와 메타데이터, 정규화·가공 데이터, 평가 데이터를 보관한다.

## 담당 데이터 (3구분)

- **입력 데이터**: 계약서, 특약, 등기사항증명서, 건축물대장 등 (실제 데이터는 Git 제외)
- **분석 기준 데이터**: 관련 법령, 표준 주택임대차계약서, 공공기관 가이드, 문서 필드 정의, 문서 비교 규칙
- **결과 데이터**: 확인 필요 항목, 질문, 체크리스트, 계약 직후 행동, 미완료 항목, 결과 리포트

## 하위 구조

```
raw/                    실제 원본 (Git 제외, README만 커밋)
sample/                 비식별 샘플
  contracts/ registry-records/ building-ledgers/ expected-results/
processed/              가공 산출물
  normalized-documents/ extracted-fields/
schemas/                문서 필드 스키마
rules/                  문서 비교 규칙 (정의는 docs/data/rule-definition.md)
rag/                    sources/ metadata/ chunks/
evaluation/             extraction/ rules/ retrieval/ generation/ end-to-end/
```

## 저장해야 하는 파일

- 가상·비식별 샘플, 필드 스키마, 규칙 데이터, 공식 RAG 자료·메타데이터, 평가 데이터

## 저장하면 안 되는 파일

- 실제 계약서·개인정보 (이름·주소·연락처·계좌번호 등)
- 생성된 대용량 벡터 인덱스 (→ Git 제외)

## 다른 폴더와의 연결

- `ai/`가 스키마·규칙·RAG 자료·평가 데이터를 참조한다.
- 데이터 설계 문서는 `docs/data/`.

## 현재 상태 / TODO

- 폴더 구조만 존재. 실제 데이터 없음.
- TODO: 문서 필드 스키마 초안 (`docs/data/document-fields.md` 기반)
- TODO: 규칙 데이터 정의 (`docs/data/rule-definition.md` 기반)
- TODO: 공식 RAG 출처 수집·메타데이터 기록 (`docs/data/rag-sources.md` 기준)
- TODO: 평가 데이터셋 구성 (`docs/ai/evaluation-plan.md` 기준)
