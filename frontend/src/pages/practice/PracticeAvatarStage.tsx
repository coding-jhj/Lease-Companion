import { useEffect, useRef, useState } from "react";

type AvatarMode = "idle" | "speaking" | "listening" | "pressure";

const avatarVideos: Record<AvatarMode, string> = {
  idle: "/practice/avatar/idle.mp4",
  speaking: "/practice/avatar/speaking.mp4",
  listening: "/practice/avatar/listening.mp4",
  pressure: "/practice/avatar/pressure.mp4",
};

const avatarLabels: Record<AvatarMode, string> = {
  idle: "대화를 준비하고 있습니다",
  speaking: "공인중개사가 말하고 있습니다",
  listening: "답변을 듣고 있습니다",
  pressure: "공인중개사가 결정을 재촉하고 있습니다",
};

interface PracticeAvatarStageProps {
  prompt: string;
  pressureDelaySeconds: number | null;
  hasUserInput: boolean;
  submitting: boolean;
}

export function PracticeAvatarStage({
  prompt,
  pressureDelaySeconds,
  hasUserInput,
  submitting,
}: PracticeAvatarStageProps) {
  const [mode, setMode] = useState<AvatarMode>("idle");
  const [playbackId, setPlaybackId] = useState(0);
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

  return (
    <section className="practice-avatar-stage" aria-labelledby="practice-avatar-title">
      <div className="practice-avatar-stage__video-wrap">
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
        />
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
