# 계약 연습 시뮬레이션 미디어 제공자 조사

- 조사일: 2026-07-20
- 갱신: 2026-07-23
- 상태: 로컬 MVP 출력 경로는 Supertonic 3 + MuseTalk 1.5로 확정. 아래 상용 후보는 품질·운영 비교 자료로 유지
- 전제: 캐릭터 기준 이미지는 Gemini로 만들고 영상은 상태별 짧은 클립으로 사전 제작한다.

## 결론

로컬·비식별 실행이 가능한 첫 통합 경로로 `Supertonic 3 → MuseTalk 1.5`를 채택했다. 실제 목소리 복제 없이 Supertonic 기본 음성을 사용하고, MuseTalk 결과는 답변별 비동기 작업으로 생성한다. 선택 근거와 성능 제한은 [`../decisions/2026-07-23-practice-avatar-media-pipeline.md`](../decisions/2026-07-23-practice-avatar-media-pipeline.md)를 따른다.

영상과 음성을 한 제공자로 통일하지 않는다. 필요한 품질에 따라 다음 후보를 별도로 비교한다.

1. 대사 없는 대기·압박 동작: `Veo 3.1 Standard`, `Runway Gen-4.5`, `Luma Ray3.2`
2. 대사와 정확한 표정·손짓: `Runway Act-Two`, `HeyGen Avatar IV`, `Higgsfield Lipsync Studio`
3. 한국어 음성: `ElevenLabs Eleven v3/Multilingual v2`, `Cartesia Sonic-3.5`, `Azure Speech`

품질 우선 가설은 다음과 같다.

- 기준 동작을 촬영할 수 있으면 `Gemini 이미지 → ElevenLabs 음성 → Runway Act-Two`가 구체적인 손짓과 표정을 가장 통제하기 쉽다.
- 촬영하지 않으면 말하는 장면은 `HeyGen Avatar IV`, 대기·환경 동작은 `Veo 3.1 Standard` 또는 `Runway Gen-4.5` 조합이 유력하다.
- 이는 공식 기능을 바탕으로 한 가설이다. 동일 입력의 블라인드 비교 전에는 주력 제공자로 확정하지 않는다.

## 영상 후보

| 후보 | 가격·무료 범위 | 강점 | 제한 | 용도 |
|---|---|---|---|---|
| Veo 3.1 Standard | API 유료. 720/1080p 약 `$0.40/초`, 4K `$0.60/초` | 시작·끝 프레임, 참조 이미지, 16:9·9:16, 네이티브 오디오 | 전용 대화 아바타가 아니며 8초 중심 | 대기·압박 루프 1차 후보 |
| Runway Gen-4.5 | Standard 이상, `12 credits/초` | 복합 순서·카메라·미세 동작 지시 | 결과 편차로 반복 생성 필요 | 일반 동작 1차 후보 |
| Runway Act-Two | `5 credits/초`, 최대 30초 | 기준 동작 영상의 말·표정·손짓을 캐릭터로 전이 | 사람이 기준 동작을 촬영해야 함 | 정밀 연기 1차 후보 |
| HeyGen Avatar IV | 제한 무료 체험. API Photo Avatar 720/1080p `$0.05/초` | 이미지와 대본·음성만으로 립싱크·표정·제스처 생성 | 계약서 넘김 같은 물체 상호작용은 제한 가능 | 말하는 장면 1차 후보 |
| Luma Ray3.2 | Plus `$30/월`; API 720p 5초 `$0.30`, 10초 `$0.90` | 최대 16 키프레임, 영상 수정·리프레임, 1080p | 립싱크 전용 모델이 아님 | 장면 연속성 비교 후보 |
| Higgsfield | 공개 가격과 크레딧이 자주 변해 결제 전 재확인 필요 | Lipsync Studio와 여러 영상 모델을 한 흐름에서 사용 | Soul ID는 실제 인물 사진 중심이라 합성 인물 적합성 검증 필요 | 통합 제작 흐름 후보 |
| Adobe Firefly | 제한 무료. Standard 약 `$9.99/월`부터 | Firefly·Veo·Runway·Luma·Kling 등 여러 모델 비교 가능 | 파트너 모델별 조건이 따로 적용 | 비교 작업공간·상업 안전 후보 |
| Pika | 무료 월 크레딧, Standard 약 `$8/월`부터 | 저비용·빠른 시안 | 사실적 대화·캐릭터 일관성보다 짧은 효과 영상에 적합 | 초기 시안 후보 |
| Sora 2 | API `$0.10/초`, Pro `$0.30/초` | 이미지 입력과 동기 오디오 | API 종료 예정과 사람 얼굴 입력 제한이 현재 방식과 충돌 | 제외 |

`Kling 3.0/Omni`, `Seedance 2.0`은 합성 입력 품질 벤치마크 후보로만 둔다. 프로젝트 지침에 따라 중국계 제공자는 입력 보존·학습·상업 이용·개인정보 조건을 별도 검토하고 사용자 승인을 받기 전 운영 후보에 포함하지 않는다.

## 한국어 음성 후보

| 후보 | 가격·무료 범위 | 강점 | 용도 |
|---|---|---|---|
| ElevenLabs Eleven v3 | 무료 10,000자 수준, API Starter `$6/월`부터. 상업 이용은 유료 | 감정 표현, 오디오 태그, 다화자, 한국어 | 압박·회피 대사 1차 후보 |
| ElevenLabs Multilingual v2 | 동일 계정·과금 | 장문 안정성·일관성, 한국어 | 기본 중개사 목소리 1차 후보 |
| Cartesia Sonic-3.5 | Free 약 27분/월, Pro `$5/월` 약 133분·상업 이용 | 저지연과 낮은 유료 진입비 | 1차 경쟁 후보 |
| Azure Speech | 사용량 기반 | 한국어 Neural HD·다국어·감정 스타일 음성 다수 | 1차 경쟁 후보 |
| Google Chirp 3 HD | 월 100만 자 구간 기준 `$30/100만 자` | 한국어 GA, 발음·일관성 중심 운영 | 안정적 대체 후보 |
| OpenAI GPT-4o mini TTS | 무료 API 미지원, 토큰 기반 과금 | 자연어 말투 지시 | 비교 후보 |
| Amazon Polly Neural | 첫 12개월 월 100만 자 무료, 이후 `$16/100만 자` | 한국어 음성·서울 리전·저렴한 운영 | 운영 대체 후보 |
| Gemini TTS Preview | API 과금, 한국어 지원 | 톤·속도·스타일 자연어 제어 | 실험 후보, 운영 주력 보류 |

실제 인물 음성 복제는 사용하지 않는다. 제공자 기본 음성 또는 텍스트로 설계한 합성 음성만 사용하고 목소리 ID·모델 버전·설정값을 미디어 manifest에 기록한다.

## 비교 실험

고정 입력은 Gemini 기준 이미지 1장, 중립·재촉·긍정 표정 참고 이미지, 동일 대사, 동일 동작으로 구성한다.

대표 대사:

> 다른 사람도 보러 오기로 했어요. 지금 결정하셔야 합니다.

대표 동작:

> 눈 맞춤 → 시계 확인 → 손가락 두드림 → 계약서 쪽으로 손짓

출력은 1080p·5~8초·16:9로 통일한다. 모바일은 단순 중앙 자르기로 끝내지 않고 9:16 별도 생성 또는 리프레임 결과를 검수한다.

### 영상 평가 100점

| 항목 | 배점 |
|---|---:|
| 기준 얼굴·의상·공간 보존 | 25 |
| 손·계약서·시계의 물리 자연스러움 | 20 |
| 지시 동작 정확성 | 20 |
| 표정과 압박 강도 자연스러움 | 15 |
| 루프 시작·끝 연결 | 10 |
| PC·모바일 크롭 안정성 | 10 |

### 음성 평가 100점

| 항목 | 배점 |
|---|---:|
| 한국어 발음·숫자·부동산 용어 정확성 | 30 |
| 사람 같은 호흡·속도·억양 | 25 |
| 압박하되 위협적이지 않은 감정 | 20 |
| 여러 문장 간 동일 인물 일관성 | 15 |
| 영상 립싱크 적합성 | 10 |

모델마다 최소 3회 생성하고 평가자에게 모델명을 숨긴다. 워터마크 없음, 상업 이용 가능, 입력·출력 학습 사용 조건 확인을 하드 게이트로 둔다.

## 권장 비교 순서

1. 음성: ElevenLabs v3, Multilingual v2, Cartesia Sonic-3.5
2. 대화 영상: Runway Act-Two, HeyGen Avatar IV, Higgsfield Lipsync Studio
3. 대기 영상: Veo 3.1 Standard, Runway Gen-4.5, Luma Ray3.2
4. 블라인드 점수·성공률·시도 횟수·실제 비용 기록
5. `주력`, `대체`, `탈락`을 별도 ADR로 확정

무료 체험은 UI와 입력 호환성 확인에 사용한다. 최종 비교 출력은 동일한 1080p·워터마크 없음·상업 이용 조건으로 맞춘다. 실제 결제·API 연결 직전에 가격과 Preview 상태를 다시 확인한다.

## 공식 출처

- [Google Veo](https://ai.google.dev/gemini-api/docs/veo), [Gemini API 가격](https://ai.google.dev/gemini-api/docs/pricing)
- [Runway Gen-4.5](https://help.runwayml.com/hc/en-us/articles/46974685288467-Creating-with-Gen-4-5), [Runway 가격](https://runwayml.com/pricing)
- [HeyGen Avatar IV](https://www.heygen.com/blog/announcing-the-avatar-iv-api), [HeyGen API 가격](https://developers.heygen.com/docs/pricing)
- [Luma Ray3.2 API와 가격](https://lumalabs.ai/api)
- [Adobe Firefly 파트너 영상 모델](https://helpx.adobe.com/firefly/web/work-with-audio-and-video/work-with-video/generate-videos-using-non-adobe-models.html)
- [ElevenLabs TTS 모델](https://elevenlabs.io/docs/eleven-creative/playground/text-to-speech), [ElevenLabs API 가격](https://elevenlabs.io/pricing/api)
- [Cartesia 가격](https://www.cartesia.ai/pricing)
- [Azure Speech 한국어 음성](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support)
- [Google Cloud TTS 가격](https://cloud.google.com/text-to-speech/pricing)
- [Amazon Polly 가격](https://aws.amazon.com/polly/pricing/)
- [OpenAI GPT-4o mini TTS](https://developers.openai.com/api/docs/models/gpt-4o-mini-tts)
