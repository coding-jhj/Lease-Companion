# 계약 연습 로컬 아바타 미디어 파이프라인

- 날짜: 2026-07-23
- 상태: 로컬 MVP 확정

## 배경

계약 연습의 텍스트 답변을 말하는 아바타로 재생하되, 계약 판정·답변 평가와 미디어 provider 장애를 분리해야 한다. 로컬 MVP는 실제 인물 음성 복제나 외부 미디어 API로 개인정보를 보내지 않고 검증할 수 있어야 한다.

## 결정

- 음성합성은 여성 아바타와 일치하는 `Supertonic 3` 기본 음성 `F1`, 언어 `ko`를 사용한다.
- 립싱크는 `MuseTalk 1.5`와 검수된 정면·중립·무음 소스 `frontend/public/practice/avatar/musetalk-source.mp4`를 Backend 생성 입력으로만 사용한다. Frontend 생성 대기 화면은 기존 상태별 `idle`·`speaking`·`listening`·`pressure` 루프를 유지한다.
- Backend는 TURN 답변 저장 후 별도 `PracticeMediaJob`을 만들고 웹 요청과 분리된 자식 프로세스에서 WAV와 MP4를 순서대로 생성한다. GPU 작업은 프로세스 간 잠금으로 직렬화한다.
- Frontend는 작업 상태를 폴링하고 완료된 인증 MP4를 재생한다.
- 기능 플래그 `PRACTICE_MEDIA_ENABLED`는 기본 `false`다. 미디어 작업 실패·timeout은 계약 규칙 판정, 사용자 답변 평가, TURN 상태를 바꾸지 않으며 텍스트와 기존 영상으로 복구한다.
- 음성·영상 파일은 Git에서 제외한 로컬 미디어 저장소에 둔다. 운영 저장소·CDN과 수명 정책은 별도 결정한다.
- STT, 실시간 음성 입력, 실제 인물 목소리 복제는 이 결정의 범위가 아니다.

## 검증 결과

RTX 3070 8GB Windows 환경에서 한국어 Supertonic 3 WAV와 MuseTalk 1.5 MP4의 실제 생성을 확인했다.

- TTS: 7.31초, 44.1kHz mono WAV를 약 3.64초에 생성
- 립싱크: 1280×720, 25fps, H.264/AAC, 7.31초 MP4 생성
- MuseTalk 최초 일반 inference: 모델 로드와 얼굴 전처리를 포함해 약 235초

따라서 현재 구현은 기능 검증용 비동기 MVP다. 대화형 지연시간을 만족하려면 MuseTalk 모델을 상주시킨 영속 GPU worker와 avatar 좌표·latent·mask 사전 처리 cache가 필요하다. 실측 전에는 이를 실시간 아바타로 표현하지 않는다.

## 설정

필수 설정과 기본값은 [`../../backend/.env.example`](../../backend/.env.example)에 기록한다.

- Supertonic: `SUPERTONIC_VOICE`, `SUPERTONIC_LANGUAGE`, `SUPERTONIC_TOTAL_STEPS`, `SUPERTONIC_SPEED`
- MuseTalk: `MUSETALK_ROOT`(소스), `MUSETALK_ASSET_ROOT`(선택적 모델·상대경로 자산 루트), `MUSETALK_PYTHON`, `MUSETALK_SOURCE_AVATAR`, `MUSETALK_UNET_MODEL_PATH`, `MUSETALK_UNET_CONFIG`
- 실행: `MUSETALK_VERSION`, `MUSETALK_USE_FLOAT16`, `MUSETALK_BATCH_SIZE`, `PRACTICE_MEDIA_TIMEOUT_SECONDS`

## 영향과 제한

- 미디어 작업은 연습 세션·TURN의 소유권을 따라 조회하며 다른 사용자의 파일은 제공하지 않는다.
- 로컬 모델 파일과 생성물은 저장소에 커밋하지 않는다.
- 현재 로컬 자식 프로세스 방식은 서버 재시작 후 queued 작업 복구와 여러 호스트의 worker 조율을 제공하지 않는다.
- MuseTalk와 Supertonic의 라이선스·고지 조건은 배포 전에 다시 검토한다. 로컬 실행이 공식 호스팅 서비스의 지원 종료와 독립적이어도, 라이선스와 의존성 유지보수 위험까지 사라지는 것은 아니다.
