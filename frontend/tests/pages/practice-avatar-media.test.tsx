// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PracticeAvatarStage } from "../../src/pages/practice/PracticeAvatarStage";


describe("PracticeAvatarStage generated media", () => {
  it("plays a completed authenticated media blob with audio controls", () => {
    const view = render(
      <PracticeAvatarStage
        prompt="다음 확인 질문입니다."
        pressureDelaySeconds={null}
        hasUserInput={false}
        submitting={false}
        generatedVideoUrl="blob:practice-media"
        generatedSpeechText="확인 요청을 반영했습니다."
        mediaStatus="completed"
      />,
    );

    const video = view.container.querySelector("video");
    expect(video).toHaveAttribute("src", "blob:practice-media");
    expect(video).toHaveAttribute("controls");
    expect(video).not.toHaveAttribute("muted");
    expect(screen.getByRole("heading", { name: "확인 요청을 반영했습니다." })).toBeInTheDocument();
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

    expect(screen.getByText("입 모양을 음성에 맞추고 있습니다.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "계약 조건을 확인하시겠습니까?" })).toBeInTheDocument();
  });
});
