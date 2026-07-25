# 로컬 계약 연습 아바타 준비

구현 경로는 `Supertonic 3 → speech.wav → MuseTalk 1.5 → speaking.mp4`다. 모델·가중치·생성물은 Git에 커밋하지 않는다.

## 검증된 Windows 구성

- Python 3.10 MuseTalk 전용 가상환경
- PyTorch 2.0.1 + CUDA 11.8
- MuseTalk 1.5 공식 가중치
- `yapf==0.40.1` (`mmcv` 설정 로딩과 최신 YAPF의 Windows 임시 파일 충돌 회피)
- ffmpeg 실행 파일

Supertonic은 Backend 가상환경에 설치하고 최초 실행에서 모델을 로컬 cache에 내려받는다. MuseTalk는 공식 저장소의 설치·가중치 안내를 따라 별도 디렉터리에 준비한 뒤 [`../../backend/.env.example`](../../backend/.env.example)의 경로를 맞춘다.

준비가 끝난 뒤에만 `PRACTICE_MEDIA_ENABLED=true`로 바꾼다. Backend는 MuseTalk 전용 Python 프로세스를 상주시켜 모델을 한 번만 올리고, 25fps·4초 입력으로 만든 avatar 좌표·latent·mask cache를 재사용한다. 시작 시 Supertonic과 MuseTalk 전체 경로를 background warm-up하므로 API 준비 직후에는 미디어 상태가 잠시 `queued`로 유지될 수 있다.

`MUSETALK_SOURCE_AVATAR`는 정면·중립 입 모양의 무음 영상으로 지정한다. 현재 검수된 프로젝트 소스는 `frontend/public/practice/avatar/musetalk-source.mp4`이며 Backend 생성 입력 전용이다. Frontend 상태별 루프는 기존 `idle.mp4`·`speaking.mp4`·`listening.mp4`·`pressure.mp4`를 유지한다.

## 다른 Windows 서버 준비

모델과 가중치는 Git에 포함하지 않는다. 새 서버에서는 저장소 루트에서 다음 준비 명령을 한 번 실행한다.

```powershell
& .\scripts\avatar\setup-musetalk-windows.ps1
```

스크립트는 공식 MuseTalk 저장소의 검증된 commit을 `tmp/MuseTalk`에 checkout하고, Python 3.10 전용 환경·CUDA 11.8용 PyTorch·공식 의존성·가중치를 준비한 뒤 CUDA와 필수 파일을 검증한다. 검증이 끝나면 기존 `backend/.env`의 다른 설정은 보존하면서 MuseTalk 경로와 `PRACTICE_MEDIA_ENABLED=true`를 반영한다. Python 환경이나 가중치를 이미 준비했다면 각각 `-SkipDependencies`, `-SkipWeights`를 사용할 수 있다.

준비 상태만 다시 확인하려면 다음 명령을 사용한다.

```powershell
& .\scripts\avatar\verify-musetalk.ps1
```

설치 스크립트가 완료되면 FastAPI만 재시작한다. `.env.example`의 MuseTalk 경로는 저장소 기준 상대경로이므로 특정 사용자 홈이나 드라이브 문자에 의존하지 않는다.

## 16초 생성 목표

- RTX 3070 8GB 검증 기본값은 FP16, batch 12, 25fps, NVENC 우선이다. NVENC를 사용할 수 없으면 `libx264 ultrafast`로 자동 복구한다.
- 화면의 전체 답변은 유지하되 아바타 발화는 두 문장·65자 이내로 제한한다. 기본 TTS 속도는 `1.1`이며 WAV가 9초보다 길면 문장을 자르지 않고 `atempo`로 9초 예산에 맞춘다.
- 같은 avatar cache와 상주 모델을 사용하는 warm 경로만 16초 목표의 대상이다. 최초 모델 적재·avatar cache 생성은 준비 시간으로 분리한다.
- 생성 시간은 `PracticeMediaJob.settings_payload.timings_ms`와 `target_met`에 저장한다.

관련 설정은 `PRACTICE_MEDIA_WARM_ON_STARTUP`, `PRACTICE_MEDIA_MAX_SPEECH_CHARS`, `PRACTICE_MEDIA_MAX_AUDIO_SECONDS`, `MUSETALK_BATCH_SIZE`, `MUSETALK_FPS`, `MUSETALK_AVATAR_SECONDS`, `MUSETALK_EXTRA_MARGIN`, `MUSETALK_PARSING_MODE`, `MUSETALK_LEFT_CHEEK_WIDTH`, `MUSETALK_RIGHT_CHEEK_WIDTH`, `MUSETALK_VIDEO_ENCODER`다. 현재 초기 마스크 튜닝값은 아래쪽 크롭 여백 `8`, `jaw` 파싱, 좌우 볼 너비 `80`이며 볼 너비도 avatar cache 식별자에 포함되어 값이 바뀌면 좌표·latent·mask를 다시 준비한다.
