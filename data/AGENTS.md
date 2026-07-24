# data/AGENTS.md

`data/` 전용 지시서. 루트 [`../AGENTS.md`](../AGENTS.md)를 전제로 하며, 여기서는 데이터 고유 규칙만 정의한다.

## 커밋 금지

- 실제 계약서·개인정보(이름·주소·연락처·주민등록번호·계좌번호 등)를 커밋하지 않는다.
- `data/raw` 내부 실제 데이터는 Git에서 제외한다. (`data/raw/README.md`만 예외)
- `data/processed/**`는 Git 제외한다. (각 폴더 `README.md`만 예외)
- **모델 가중치·체크포인트·어댑터 파일을 커밋하지 않는다.** `data/model-metadata/`에는 메타데이터만 둔다.
- 대용량 벡터 인덱스(`*.faiss`·`*.index`·`chroma/` 등)를 커밋하지 않는다.
- 세부 개인정보 원칙: [`../docs/data/privacy-policy.md`](../docs/data/privacy-policy.md).

## 샘플·데이터셋

- `sample/`·`datasets/`에는 **가상 또는 완전히 비식별화한 데이터만** 둔다.
- 실제 자료와 생성·합성 데이터를 명확히 구분한다.
- 실제 원본에서 파생한 비식별본은 재식별 불가함을 확인한 뒤 둔다.

## RAG / 분석 기준 자료

- 공식 법령·표준 주택임대차계약서·공공기관 자료를 우선한다. 블로그·카페·커뮤니티 자료를 핵심 근거로 사용하지 않는다.
- RAG 자료마다 필수 메타데이터를 기록한다: **자료명·발행기관·조문/항목·시행일·원문 URL·수집일·문서 유형.** (`rag/metadata/`, 기준: [`../docs/data/rag-sources.md`](../docs/data/rag-sources.md))

## 데이터 구분·불변성

- 원본(`raw`)·정제본(`processed`)·청크(`rag/chunks`)·평가 데이터(`evaluation`)를 구분한다.
- 원본 데이터를 직접 덮어쓰지 않는다. 가공은 별도 산출물로 남긴다.
- 파인튜닝 데이터는 `source→labeled→train/validation/test`로 분리하고, 동일 문장이 여러 분할에 중복되지 않게 한다. (기준: [`../docs/data/training-dataset.md`](../docs/data/training-dataset.md))

## 규칙·라벨·판정 데이터

- 규칙마다 **규칙 ID·연결 판정(J01–J13)·적용 단계·입력 필드·조건·결과 상태·시급도·근거·버전**을 기록한다. (기준: [`../docs/data/rule-definition.md`](../docs/data/rule-definition.md), 판정: [`../docs/data/judgment-spec.md`](../docs/data/judgment-spec.md))
- 결과 상태는 공통 9개(`일치·불일치·명확·불명확·미기재·상충 가능·확인 필요·확인 불가·적용 제외`)만 사용한다. 판정별 허용 집합은 판정 명세를 따른다.
- 라벨 5종(`clause_type·clarity·responsible_party·condition·review_required`)의 정의·경계 사례를 `labels/`에 문서화한다.
