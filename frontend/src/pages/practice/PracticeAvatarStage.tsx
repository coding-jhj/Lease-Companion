import { useEffect, useRef, useState } from "react";
import { practiceMediaForScenario, sharedPoster } from "./practiceMediaManifest";

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

function prefersReducedMotion() {
  return window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches ?? false;
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
  const [reducedMotion] = useState(prefersReducedMotion);
  const [userPlaybackRequested, setUserPlaybackRequested] = useState(false);
  const pressurePlayedForPrompt = useRef<string | null>(null);
  const playbackFailed = useRef(false);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const source = avatarVideos[mode];
  const hasVideo = Boolean(source);

  function requestPlayback() {
    if (!videoRef.current || !hasVideo) return;
    try {
      const result = videoRef.current.play();
      if (result) void result.catch(() => setVideoUnavailable(true));
    } catch {
      setVideoUnavailable(true);
    }
  }

  useEffect(() => {
    pressurePlayedForPrompt.current = null;
    playbackFailed.current = false;
    setMode("speaking");
    setPlaybackId((current) => current + 1);
    setVideoUnavailable(false);
  }, [prompt]);

  useEffect(() => {
    if (!hasVideo) return;
    if (!reducedMotion || userPlaybackRequested) {
      requestPlayback();
      setUserPlaybackRequested(false);
    }
  }, [hasVideo, mode, playbackId, reducedMotion, userPlaybackRequested]);

  useEffect(() => {
    if (mode !== "listening" || pressureDelaySeconds === null || hasUserInput || pressurePlayedForPrompt.current === prompt) return;
    const timer = window.setTimeout(() => {
      pressurePlayedForPrompt.current = prompt;
      setMode("pressure");
      setPlaybackId((current) => current + 1);
    }, pressureDelaySeconds * 1000);
    return () => window.clearTimeout(timer);
  }, [hasUserInput, mode, pressureDelaySeconds, prompt]);

  function replayPrompt() {
    playbackFailed.current = false;
    setVideoUnavailable(false);
    setMode("speaking");
    setUserPlaybackRequested(true);
    setPlaybackId((current) => current + 1);
  }

  function handleEnded() {
    if (mode === "speaking" || mode === "pressure") setMode("listening");
  }

  function handleVideoError() {
    playbackFailed.current = true;
    setVideoUnavailable(true);
  }

  const fallbackMessage = !hasVideo
    ? "재생할 영상을 찾지 못했습니다. 아래 대사로 연습을 계속할 수 있습니다."
    : videoUnavailable
      ? "영상을 재생하지 못했습니다. 아래 대사로 연습을 계속할 수 있습니다."
      : null;

  return (
    <section className="practice-avatar-stage" aria-labelledby="practice-avatar-title">
      <div className={`practice-avatar-stage__video-wrap${fallbackMessage ? " practice-avatar-stage__video-wrap--fallback" : ""}`}>
        {hasVideo && (
          <video
            ref={videoRef}
            key={`${mode}-${playbackId}`}
            data-testid="practice-video"
            className="practice-avatar-stage__video"
            src={source}
            poster={sharedPoster}
            autoPlay={!reducedMotion}
            muted
            playsInline
            loop={mode === "idle" || mode === "listening"}
            preload="auto"
            onEnded={handleEnded}
            onAbort={handleVideoError}
            onError={handleVideoError}
          onPlaying={() => {
            if (!playbackFailed.current) {
              setVideoUnavailable(false);
            }
          }}
          />
        )}
        {fallbackMessage && <p className="practice-avatar-stage__video-fallback" role="status">{fallbackMessage}</p>}
        <span className={`practice-avatar-stage__status practice-avatar-stage__status--${mode}`} role="status" aria-live="polite">
          {avatarLabels[mode]}
        </span>
      </div>
      <div className="practice-avatar-stage__caption">
        <div>
          <p>공인중개사</p>
          <h2 id="practice-avatar-title">{prompt}</h2>
        </div>
        <button type="button" className="secondary practice-avatar-stage__retry" onClick={replayPrompt} disabled={submitting}>
          {reducedMotion ? "장면 재생" : "장면 다시 보기"}
        </button>
      </div>
    </section>
  );
}
