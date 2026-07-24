# 로컬 계약 연습 아바타 준비

구현 경로는 `Supertonic 3 → speech.wav → MuseTalk 1.5 → speaking.mp4`다. 모델·가중치·생성물은 Git에 커밋하지 않는다.

## 검증된 Windows 구성

- Python 3.10 MuseTalk 전용 가상환경
- PyTorch 2.0.1 + CUDA 11.8
- MuseTalk 1.5 공식 가중치
- `yapf==0.40.1` (`mmcv` 설정 로딩과 최신 YAPF의 Windows 임시 파일 충돌 회피)
- ffmpeg 실행 파일

Supertonic은 Backend 가상환경에 설치하고 최초 실행에서 모델을 로컬 cache에 내려받는다. MuseTalk는 공식 저장소의 설치·가중치 안내를 따라 별도 디렉터리에 준비한 뒤 [`../../backend/.env.example`](../../backend/.env.example)의 경로를 맞춘다.

준비가 끝난 뒤에만 `PRACTICE_MEDIA_ENABLED=true`로 바꾼다. 현재 일반 MuseTalk inference는 모델 로드와 avatar 전처리를 매 작업 반복하므로 비동기 기능 검증용이며, 실시간 서비스에는 영속 GPU worker와 사전 처리 cache가 추가로 필요하다.

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
