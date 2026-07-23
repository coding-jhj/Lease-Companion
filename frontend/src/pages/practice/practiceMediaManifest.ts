type PracticeAvatarMode = "idle" | "speaking" | "listening" | "pressure";
export type PracticeMediaSet = Record<PracticeAvatarMode, string>;

export const sharedPoster = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 640 360'%3E%3Crect width='640' height='360' fill='%2317251c'/%3E%3Ctext x='320' y='180' text-anchor='middle' fill='%23ffffff' font-size='28'%3E%EA%B3%84%EC%95%BD%20%EC%97%B0%EC%8A%B5%3C/text%3E%3C/svg%3E";

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
