// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { PracticeAvatarStage } from "../../src/pages/practice/PracticeAvatarStage";

afterEach(cleanup);

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
      screen.getByText("영상을 재생할 수 없어 아래 대사와 안내 문구로 계속 진행합니다."),
    ).toBeInTheDocument();
    // 대사와 장면 다시 보기는 오류 후에도 계속 사용할 수 있어야 미션이 막히지 않는다.
    expect(screen.getByRole("heading", { name: baseProps.prompt })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "장면 다시 보기" })).toBeEnabled();
  });

  it("clears the fallback once a video starts playing", () => {
    render(<PracticeAvatarStage {...baseProps} />);
    const video = document.querySelector("video") as HTMLVideoElement;

    fireEvent.error(video);
    expect(screen.getByText(/영상을 재생할 수 없어/)).toBeInTheDocument();

    // 오류 후 발화→경청 전환으로 video가 remount되므로 현재 요소를 다시 조회한다.
    const currentVideo = document.querySelector("video") as HTMLVideoElement;
    fireEvent.playing(currentVideo);
    expect(screen.queryByText(/영상을 재생할 수 없어/)).not.toBeInTheDocument();
  });
});
