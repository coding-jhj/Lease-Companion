import { useEffect, useRef, useState } from "react";
import { practiceMediaForScenario } from "./practiceMediaManifest";
import type { PracticeMediaStatus } from "../../types/api";

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
  generatedVideoUrl?: string | null;
  generatedSpeechText?: string | null;
  mediaStatus?: PracticeMediaStatus | null;
}

export function PracticeAvatarStage({
  scenarioId,
  prompt,
  pressureDelaySeconds,
  hasUserInput,
  submitting,
  generatedVideoUrl = null,
  generatedSpeechText = null,
  mediaStatus = null,
}: PracticeAvatarStageProps) {
  const avatarVideos = practiceMediaForScenario(scenarioId);
  const [mode, setMode] = useState<AvatarMode>("idle");
  const [playbackId, setPlaybackId] = useState(0);
  const pressurePlayedForPrompt = useRef<string | null>(null);

  useEffect(() => {
    pressurePlayedForPrompt.current = null;
    setMode("speaking");
    setPlaybackId((current) => current + 1);
  }, [prompt]);

  useEffect(() => {
    if (!generatedVideoUrl) return;
    setMode("speaking");
    setPlaybackId((current) => current + 1);
  }, [generatedVideoUrl]);

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

  const isGeneratedSpeech = mode === "speaking" && Boolean(generatedVideoUrl);
  const videoSource = isGeneratedSpeech ? generatedVideoUrl! : avatarVideos[mode];
  const caption = isGeneratedSpeech && generatedSpeechText ? generatedSpeechText : prompt;

  function handleEnded() {
    if (mode === "speaking" || mode === "pressure") setMode("listening");
  }

  return (
    <section className="practice-avatar-stage" aria-labelledby="practice-avatar-title">
      <div className="practice-avatar-stage__video-wrap">
        <video
          key={`${mode}-${playbackId}`}
          className="practice-avatar-stage__video"
          src={videoSource}
          autoPlay
          muted={!isGeneratedSpeech}
          controls={isGeneratedSpeech}
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
          <h2 id="practice-avatar-title">{caption}</h2>
          {(mediaStatus === "queued" || mediaStatus === "generating_audio" || mediaStatus === "generating_video") && (
            <span className="practice-avatar-stage__media-state" role="status">
              {mediaStatus === "queued" && "아바타 응답을 준비하고 있습니다."}
              {mediaStatus === "generating_audio" && "응답 음성을 만들고 있습니다."}
              {mediaStatus === "generating_video" && "입 모양을 음성에 맞추고 있습니다."}
            </span>
          )}
          {mediaStatus === "failed" && (
            <span className="practice-avatar-stage__media-state">영상 생성에 실패해 텍스트 응답을 표시합니다.</span>
          )}
        </div>
        <button type="button" className="secondary" onClick={replayPrompt} disabled={submitting}>
          장면 다시 보기
        </button>
      </div>
    </section>
  );
}
