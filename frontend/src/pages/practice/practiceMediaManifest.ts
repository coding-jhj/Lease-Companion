type PracticeAvatarMode = "idle" | "speaking" | "listening" | "pressure";
type PracticeMediaSet = Record<PracticeAvatarMode, string>;

const sharedMedia: PracticeMediaSet = {
  idle: "/practice/avatar/idle.mp4",
  speaking: "/practice/avatar/speaking.mp4",
  listening: "/practice/avatar/listening.mp4",
  pressure: "/practice/avatar/pressure.mp4",
};

// 시나리오별 파일이 제작되면 경로만 교체한다. 현재 데모는 검수된 공통 상태 영상을 사용한다.
const scenarioMedia: Record<string, PracticeMediaSet> = {
  "PRACTICE-DEFERRED-REFUND-001": sharedMedia,
  "PRACTICE-THIRD-PARTY-PAYMENT-001": sharedMedia,
  "PRACTICE-PROXY-AUTHORITY-001": sharedMedia,
};

export function practiceMediaForScenario(scenarioId?: string): PracticeMediaSet {
  return (scenarioId && scenarioMedia[scenarioId]) || sharedMedia;
}
