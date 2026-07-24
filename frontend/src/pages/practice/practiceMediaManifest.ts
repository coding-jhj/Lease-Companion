type PracticeAvatarMode = "idle" | "speaking" | "listening" | "pressure";
export type PracticeMediaSet = Record<PracticeAvatarMode, string>;

export const sharedPoster = "/practice/avatar/poster.jpg";

const sharedMedia: PracticeMediaSet = {
  idle: "/practice/avatar/idle.mp4",
  speaking: "/practice/avatar/speaking.mp4",
  listening: "/practice/avatar/listening.mp4",
  pressure: "/practice/avatar/pressure.mp4",
};

// 화면 상태 루프는 기존 검수 영상을 유지한다. musetalk-source.mp4는 Backend 생성 입력 전용이다.
const scenarioMedia: Record<string, PracticeMediaSet> = {
  "PRACTICE-DEFERRED-REFUND-001": sharedMedia,
  "PRACTICE-THIRD-PARTY-PAYMENT-001": sharedMedia,
  "PRACTICE-PROXY-AUTHORITY-001": sharedMedia,
};

export function practiceMediaForScenario(scenarioId?: string): PracticeMediaSet {
  return (scenarioId && scenarioMedia[scenarioId]) || sharedMedia;
}
