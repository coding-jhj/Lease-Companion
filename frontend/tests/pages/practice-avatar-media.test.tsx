// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { PracticeAvatarStage } from "../../src/pages/practice/PracticeAvatarStage";


describe("PracticeAvatarStage generated media", () => {
  beforeEach(() => {
    vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue(undefined);
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("plays a completed authenticated media blob with audio controls", () => {
    const view = render(
      <PracticeAvatarStage
        prompt="확인 요청을 반영했습니다."
        nextPrompt="다음 확인 질문입니다."
        pressureDelaySeconds={null}
        hasUserInput={false}
        submitting={false}
        generatedVideoUrl="blob:practice-media"
        mediaStatus="completed"
      />,
    );

    const video = view.container.querySelector("video");
    expect(video).toHaveAttribute("src", "blob:practice-media");
    expect(video).toHaveAttribute("controls");
    expect(video).not.toHaveAttribute("muted");
    expect(screen.queryByRole("button", { name: "립싱크 영상 보기" })).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "확인 요청을 반영했습니다." })).toBeInTheDocument();
    expect(screen.getByText("이어서 확인할 내용")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "다음 확인 질문입니다." })).toBeInTheDocument();
  });

  it("announces generation without replacing the text fallback", () => {
    render(
      <PracticeAvatarStage
        prompt="계약 조건을 확인하시겠습니까?"
        pressureDelaySeconds={null}
        hasUserInput={false}
        submitting={false}
        mediaStatus="generating_video"
      />,
    );

    expect(screen.getByText("립싱크 영상을 백그라운드에서 준비하고 있습니다.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "계약 조건을 확인하시겠습니까?" })).toBeInTheDocument();
  });

  it("plays Supertonic audio while MuseTalk is still generating", () => {
    const onEnded = vi.fn();
    render(
      <PracticeAvatarStage
        prompt="계약 조건을 다시 확인해 주세요."
        pressureDelaySeconds={null}
        hasUserInput={false}
        submitting={false}
        generatedAudioUrl="blob:supertonic-audio"
        onGeneratedAudioEnded={onEnded}
        mediaStatus="generating_video"
      />,
    );

    const audio = screen.getByLabelText("공인중개사 응답 음성");
    expect(audio).toHaveAttribute("src", "blob:supertonic-audio");
    expect(audio).toHaveAttribute("autoplay");
    expect(audio).toHaveAttribute("controls");
    audio.dispatchEvent(new Event("ended", { bubbles: true }));
    expect(onEnded).toHaveBeenCalledOnce();
  });

  it("describes MuseTalk as a background task after audio is ready", () => {
    render(
      <PracticeAvatarStage
        prompt="다음 확인 질문입니다."
        pressureDelaySeconds={null}
        hasUserInput={false}
        submitting={false}
        generatedAudioUrl="blob:supertonic-audio"
        mediaStatus="generating_video"
      />,
    );

    expect(screen.getByText("음성으로 먼저 안내합니다. 립싱크 영상은 백그라운드에서 준비합니다.")).toBeInTheDocument();
  });
});
