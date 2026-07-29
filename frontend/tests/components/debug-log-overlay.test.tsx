// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { DebugLogOverlay } from "../../src/components/debug/DebugLogOverlay";
import { clearDebugLog, debugLog, formatMediaMetrics } from "../../src/utils/debugLog";

function setSearch(search: string) {
  window.history.replaceState({}, "", `/practice/sessions/x${search}`);
}

afterEach(() => {
  cleanup();
  clearDebugLog();
  window.sessionStorage.clear();
  setSearch("");
});

describe("DebugLogOverlay", () => {
  it("주소에 debug 파라미터가 없으면 아무것도 렌더링하지 않는다", () => {
    setSearch("");
    const { container } = render(<DebugLogOverlay />);

    expect(container).toBeEmptyDOMElement();
  });

  it("debug 파라미터가 없으면 로그도 수집하지 않는다", () => {
    setSearch("");
    debugLog("STT", "꺼진 상태에서 남긴 줄");
    setSearch("?debug=1");
    render(<DebugLogOverlay />);

    // 켜진 뒤의 시작 줄만 있고, 꺼져 있을 때 호출한 로그는 남지 않는다.
    expect(screen.queryByText(/꺼진 상태에서 남긴 줄/)).not.toBeInTheDocument();
    expect(screen.getByText(/오버레이 시작/)).toBeInTheDocument();
  });

  it("debug 파라미터가 있으면 채널과 메시지를 보여준다", () => {
    setSearch("?debug=1");
    debugLog("TTS", "job=abc status=completed tts=1200ms");
    render(<DebugLogOverlay />);

    expect(screen.getByText("TTS")).toBeInTheDocument();
    expect(screen.getByText(/job=abc status=completed tts=1200ms/)).toBeInTheDocument();
  });
});

describe("디버그 플래그 유지", () => {
  it("한 번 켜면 쿼리 파라미터가 사라져도 유지된다", () => {
    setSearch("?debug=1");
    render(<DebugLogOverlay />);
    cleanup();

    // 화면 이동으로 쿼리가 날아간 상황
    setSearch("");
    render(<DebugLogOverlay />);

    expect(screen.getByText("DEBUG LOG")).toBeInTheDocument();
  });

  it("debug=0으로 끄면 다시 보이지 않는다", () => {
    setSearch("?debug=1");
    render(<DebugLogOverlay />);
    cleanup();

    setSearch("?debug=0");
    const { container } = render(<DebugLogOverlay />);
    expect(container).toBeEmptyDOMElement();

    cleanup();
    setSearch("");
    const after = render(<DebugLogOverlay />);
    expect(after.container).toBeEmptyDOMElement();
  });
});

describe("formatMediaMetrics", () => {
  it("타이밍 지표를 한 줄로 요약한다", () => {
    const line = formatMediaMetrics({
      timings_ms: { tts: 1200, video: 3400, end_to_end: 4800 },
      generated_frames: 95,
      effective_fps: 24.8,
      video_encoder: "h264_nvenc",
      target_met: true,
    });

    expect(line).toBe(
      "tts=1200ms video=3400ms frames=95 fps=24.8 encoder=h264_nvenc e2e=4800ms target_met=true",
    );
  });

  it("지표가 없으면 없다고 표시한다", () => {
    expect(formatMediaMetrics(null)).toBe("지표 없음");
  });

  it("진행 중 상태는 생성 시작 문구로 표시한다", () => {
    expect(formatMediaMetrics(null, "generating_audio")).toBe("TTS 생성 시작");
    expect(formatMediaMetrics({}, "generating_video")).toBe("립싱크 영상 생성 시작");
  });
});
