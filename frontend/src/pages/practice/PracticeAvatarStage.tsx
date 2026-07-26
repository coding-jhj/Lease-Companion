import { useEffect, useRef, useState } from "react";
import { practiceMediaForScenario, sharedPoster } from "./practiceMediaManifest";
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
  mediaStatus?: PracticeMediaStatus | null;
  onToggleConversation?: () => void;
  conversationOpen?: boolean;
}

export function PracticeAvatarStage({
  scenarioId,
  prompt,
  pressureDelaySeconds,
  hasUserInput,
  submitting,
  generatedVideoUrl = null,
  mediaStatus = null,
  onToggleConversation,
  conversationOpen = false,
}: PracticeAvatarStageProps) {
  const avatarVideos = practiceMediaForScenario(scenarioId);
  const [mode, setMode] = useState<AvatarMode>("idle");
  const [playbackId, setPlaybackId] = useState(0);
  const [videoUnavailable, setVideoUnavailable] = useState(false);
  const [playbackPaused, setPlaybackPaused] = useState(false);
  const pressurePlayedForPrompt = useRef<string | null>(null);
  const playbackFailed = useRef(false);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const isMediaPreparing = mediaStatus === "queued"
    || mediaStatus === "generating_audio"
    || mediaStatus === "generating_video"
    || (mediaStatus === "completed" && !generatedVideoUrl);
  const displayMode = isMediaPreparing ? "idle" : mode;
  const isGeneratedSpeech = displayMode === "speaking" && Boolean(generatedVideoUrl);
  const videoSource = isGeneratedSpeech ? generatedVideoUrl! : avatarVideos[displayMode];
  const hasVideo = Boolean(videoSource);

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
    if (!hasVideo || playbackPaused) return;
    requestPlayback();
  }, [hasVideo, isMediaPreparing, mode, playbackId, playbackPaused]);

  useEffect(() => {
    if (!generatedVideoUrl) return;
    playbackFailed.current = false;
    setMode("speaking");
    setPlaybackId((current) => current + 1);
    setVideoUnavailable(false);
  }, [generatedVideoUrl]);

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
    setPlaybackPaused(false);
    setPlaybackId((current) => current + 1);
  }

  function togglePlayback() {
    if (!videoRef.current || !hasVideo) return;
    if (playbackPaused) {
      setPlaybackPaused(false);
      requestPlayback();
      return;
    }
    videoRef.current.pause();
    setPlaybackPaused(true);
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
            key={`${displayMode}-${playbackId}`}
            data-testid="practice-video"
            className="practice-avatar-stage__video"
            src={videoSource}
            poster={sharedPoster}
            autoPlay={!playbackPaused}
            muted={!isGeneratedSpeech}
            controls={isGeneratedSpeech}
            playsInline
            loop={isMediaPreparing || mode === "idle" || mode === "listening"}
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
        <span className={`practice-avatar-stage__status practice-avatar-stage__status--${displayMode}`} role="status" aria-live="polite">
          {isMediaPreparing ? "공인중개사가 응답을 준비하고 있습니다" : avatarLabels[mode]}
        </span>
      </div>
      <div className="practice-avatar-stage__caption">
        <div>
          <p>공인중개사</p>
          <h2 id="practice-avatar-title">{prompt}</h2>
          {(mediaStatus === "queued" || mediaStatus === "generating_audio" || mediaStatus === "generating_video") && (
            <span className="practice-avatar-stage__media-state" role="status">
              {mediaStatus === "queued" && "아바타 응답을 준비하고 있습니다."}
              {mediaStatus === "generating_audio" && "응답 음성을 만들고 있습니다."}
              {mediaStatus === "generating_video" && "립싱크 영상을 준비하고 있습니다."}
            </span>
          )}
          {mediaStatus === "failed" && (
            <span className="practice-avatar-stage__media-state">영상 생성에 실패해 텍스트 응답을 표시합니다.</span>
          )}
        </div>
        <div className="practice-avatar-stage__controls">
          {onToggleConversation && (
            <button type="button" className="secondary practice-avatar-stage__conversation-toggle" onClick={onToggleConversation} aria-pressed={conversationOpen}>
              {conversationOpen ? "대화 닫기" : "이전 대화 보기"}
            </button>
          )}
          <button type="button" className="secondary" onClick={togglePlayback} disabled={submitting || !hasVideo}>
            {playbackPaused ? "계속 재생" : "일시정지"}
          </button>
          <button type="button" className="secondary practice-avatar-stage__retry" onClick={replayPrompt} disabled={submitting || isMediaPreparing}>
            장면 다시 보기
          </button>
        </div>
      </div>
    </section>
  );
}
