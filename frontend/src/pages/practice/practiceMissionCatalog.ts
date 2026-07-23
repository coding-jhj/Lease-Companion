export interface PracticeMission {
  title: string;
  description: string;
  guide: string;
  targetCount: number;
}

const defaultMission: PracticeMission = {
  title: "계약을 서두르지 않고 확인하기",
  description: "상대방의 제안을 바로 받아들이기 전에 필요한 내용을 자신의 말로 확인해 보세요.",
  guide: "정답 문장을 외우지 않아도 됩니다. 확인할 내용과 보류 의사가 전달되면 됩니다.",
  targetCount: 3,
};

const missions: Record<string, PracticeMission> = {
  "PRACTICE-DEFERRED-REFUND-001": {
    title: "보증금 반환 조건 확인하기",
    description: "계약서에 적힌 반환 조건을 확인하고, 충분히 확인하기 전에는 결정을 서두르지 마세요.",
    guide: defaultMission.guide,
    targetCount: 3,
  },
  "PRACTICE-THIRD-PARTY-PAYMENT-001": {
    title: "송금 요청을 받고 필요한 확인하기",
    description: "돈을 보내기 전에 누구에게 무엇을 확인해야 하는지 말하고, 확인 전 행동을 선택해 보세요.",
    guide: defaultMission.guide,
    targetCount: 3,
  },
  "PRACTICE-PROXY-AUTHORITY-001": {
    title: "대신 계약하는 사람의 권한 확인하기",
    description: "계약 상대의 권한을 확인할 자료를 요청하고, 자료를 보기 전 행동을 선택해 보세요.",
    guide: defaultMission.guide,
    targetCount: 3,
  },
};

export function practiceMissionForScenario(scenarioId: string): PracticeMission {
  return missions[scenarioId] ?? defaultMission;
}
