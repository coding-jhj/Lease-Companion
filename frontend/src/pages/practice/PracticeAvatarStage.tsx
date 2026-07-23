import { useEffect, useRef, useState } from "react";
import { practiceMediaForScenario } from "./practiceMediaManifest";

type AvatarMode = "idle" | "speaking" | "listening" | "pressure";

const avatarLabels: Record<AvatarMode, string> = {
  idle: "대화를 준비하고 있습니다",
  speaking: "공인중개사가 말하고 있습니다",
  listening: "답변을 듣고 있습니다",
  pressure: "공인중개사가 결정을 재촉하고 있습니다",
};

interface PracticeAvatarStageProps {
  scenarioId?: string;
  prompt: string;
  pressureDelaySeconds: number | null;
  hasUserInput: boolean;
  submitting: boolean;
}

export function PracticeAvatarStage({
  scenarioId,
  prompt,
  pressureDelaySeconds,
  hasUserInput,
  submitting,
}: PracticeAvatarStageProps) {
  const avatarVideos = practiceMediaForScenario(scenarioId);
  const [mode, setMode] = useState<AvatarMode>("idle");
  const [playbackId, setPlaybackId] = useState(0);
  const [videoUnavailable, setVideoUnavailable] = useState(false);
  const pressurePlayedForPrompt = useRef<string | null>(null);

  useEffect(() => {
    pressurePlayedForPrompt.current = null;
    setMode("speaking");
    setPlaybackId((current) => current + 1);
  }, [prompt]);

  useEffect(() => {
    if (
      mode !== "listening"
      || pressureDelaySeconds === null
      || hasUserInput
      || pressurePlayedForPrompt.current === prompt
    ) return;

    const timer = window.setTimeout(() => {
      pressurePlayedForPrompt.current = prompt;
      setMode("pressure");
      setPlaybackId((current) => current + 1);
    }, pressureDelaySeconds * 1000);
    return () => window.clearTimeout(timer);
  }, [hasUserInput, mode, pressureDelaySeconds, prompt]);

  function replayPrompt() {
    setMode("speaking");
    setPlaybackId((current) => current + 1);
  }

  function handleEnded() {
    if (mode === "speaking" || mode === "pressure") setMode("listening");
  }

  function handleVideoError() {
    // 영상 누락·재생 오류 시 빈 검은 화면 대신 대사·안내로 계속 진행한다.
    setVideoUnavailable(true);
    // 발화·재촉 영상이 끊겨도 답변 단계로 넘어가 미션을 막지 않는다.
    if (mode === "speaking" || mode === "pressure") setMode("listening");
  }

  return (
    <section className="practice-avatar-stage" aria-labelledby="practice-avatar-title">
      <div className={`practice-avatar-stage__video-wrap${videoUnavailable ? " practice-avatar-stage__video-wrap--fallback" : ""}`}>
        <video
          key={`${mode}-${playbackId}`}
          className="practice-avatar-stage__video"
          src={avatarVideos[mode]}
          autoPlay
          muted
          playsInline
          loop={mode === "idle" || mode === "listening"}
          preload="auto"
          onEnded={handleEnded}
          onError={handleVideoError}
          onPlaying={() => setVideoUnavailable(false)}
        />
        {videoUnavailable && (
          <p className="practice-avatar-stage__video-fallback" role="status">
            영상을 재생할 수 없어 아래 대사와 안내 문구로 계속 진행합니다.
          </p>
        )}
        <span className={`practice-avatar-stage__status practice-avatar-stage__status--${mode}`} role="status" aria-live="polite">
          {avatarLabels[mode]}
        </span>
      </div>
      <div className="practice-avatar-stage__caption">
        <div>
          <p>공인중개사</p>
          <h2 id="practice-avatar-title">{prompt}</h2>
        </div>
        <button type="button" className="secondary" onClick={replayPrompt} disabled={submitting}>
          장면 다시 보기
        </button>
      </div>
    </section>
  );
}
