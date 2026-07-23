// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { PracticeAvatarStage } from "../../src/pages/practice/PracticeAvatarStage";
import * as mediaManifest from "../../src/pages/practice/practiceMediaManifest";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

beforeEach(() => {
  vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue(undefined);
  vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(() => undefined);
});

const baseProps = {
  scenarioId: "PRACTICE-DEFERRED-REFUND-001",
  prompt: "도장을 안 가져오셨으니 계약서부터 쓰시죠.",
  pressureDelaySeconds: null,
  hasUserInput: false,
  submitting: false,
};

describe("PracticeAvatarStage", () => {
  it("falls back to text when the avatar video cannot play, without blocking the turn", () => {
    render(<PracticeAvatarStage {...baseProps} />);
    const video = document.querySelector("video");
    expect(video).not.toBeNull();

    fireEvent.error(video as HTMLVideoElement);

    expect(
      screen.getByText("영상을 재생하지 못했습니다. 아래 대사로 연습을 계속할 수 있습니다."),
    ).toBeInTheDocument();
    // 대사와 장면 다시 보기는 오류 후에도 계속 사용할 수 있어야 미션이 막히지 않는다.
    expect(screen.getByRole("heading", { name: baseProps.prompt })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "장면 다시 보기" })).toBeEnabled();
  });

  it("clears the fallback only after the user retries and a video starts playing", () => {
    render(<PracticeAvatarStage {...baseProps} />);
    const video = screen.getByTestId("practice-video") as HTMLVideoElement;

    fireEvent.error(video);
    expect(screen.getByText(/아래 대사로 연습을 계속할 수 있습니다/)).toBeInTheDocument();

    const currentVideo = screen.getByTestId("practice-video") as HTMLVideoElement;
    fireEvent.playing(currentVideo);
    expect(screen.getByText(/아래 대사로 연습을 계속할 수 있습니다/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "장면 다시 보기" }));
    fireEvent.playing(screen.getByTestId("practice-video") as HTMLVideoElement);
    expect(screen.queryByText(/아래 대사로 연습을 계속할 수 있습니다/)).not.toBeInTheDocument();
  });

  it("falls back to dialogue when a video request is aborted", () => {
    render(<PracticeAvatarStage {...baseProps} />);

    fireEvent.abort(screen.getByTestId("practice-video"));

    expect(screen.getByText("영상을 재생하지 못했습니다. 아래 대사로 연습을 계속할 수 있습니다.")).toBeInTheDocument();
    expect(screen.getByText("공인중개사가 말하고 있습니다")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: baseProps.prompt })).toBeInTheDocument();
  });

  it("uses shared media and a poster for an unregistered scenario", () => {
    render(<PracticeAvatarStage {...baseProps} scenarioId="PRACTICE-UNKNOWN-999" />);

    const video = screen.getByTestId("practice-video");
    expect(video).toHaveAttribute("src", "/practice/avatar/speaking.mp4");
    expect(video).toHaveAttribute("poster");
  });

  it("starts in text fallback without rendering an empty video source", () => {
    vi.spyOn(mediaManifest, "practiceMediaForScenario").mockReturnValue({
      idle: "", speaking: "", listening: "", pressure: "",
    });
    render(<PracticeAvatarStage {...baseProps} />);

    expect(screen.queryByTestId("practice-video")).not.toBeInTheDocument();
    expect(screen.getByText("재생할 영상을 찾지 못했습니다. 아래 대사로 연습을 계속할 수 있습니다.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: baseProps.prompt })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "장면 다시 보기" })).toBeEnabled();
  });

  it("keeps the avatar moving and gives the user an explicit pause control", () => {
    vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches: true }));
    const play = vi.mocked(HTMLMediaElement.prototype.play);
    render(<PracticeAvatarStage {...baseProps} />);

    const video = screen.getByTestId("practice-video");
    expect(video).toHaveAttribute("autoplay");
    expect(video).toHaveAttribute("poster", "/practice/avatar/poster.jpg");
    fireEvent.click(screen.getByRole("button", { name: "일시정지" }));
    expect(HTMLMediaElement.prototype.pause).toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "계속 재생" }));
    expect(play).toHaveBeenCalled();
  });

  it("keeps the prompt available after a rejected play promise and offers retry", async () => {
    vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches: false }));
    const play = vi.mocked(HTMLMediaElement.prototype.play);
    play.mockRejectedValue(new Error("blocked"));
    render(<PracticeAvatarStage {...baseProps} />);

    expect(await screen.findByText("영상을 재생하지 못했습니다. 아래 대사로 연습을 계속할 수 있습니다.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: baseProps.prompt })).toBeInTheDocument();
    const callsBeforeRetry = play.mock.calls.length;
    fireEvent.click(screen.getByRole("button", { name: "장면 다시 보기" }));
    await waitFor(() => expect(play.mock.calls.length).toBeGreaterThan(callsBeforeRetry));
  });
});
