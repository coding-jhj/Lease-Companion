import type {
  PracticeObservation,
  PracticeScenario,
  PracticeSpeaker,
} from "../types/practice";

// Backend 연습 세션 API가 연결되기 전에도 화면 흐름을 검증할 수 있는 승인 합성 fixture다.
// 실제 계약 분석 결과나 사용자 계약 문서와 섞지 않는다.
const signingPracticeScenario: PracticeScenario = {
  scenarioId: "PRACTICE-DEFERRED-REFUND-001",
  title: "서명 직전 계약 대화 연습",
  labels: ["가상 연습", "합성 시나리오"],
  situation: "당신은 전세 계약을 위해 부동산을 방문했습니다.",
  instruction:
    "계약서 내용을 확인한 뒤 공인중개사와 임대인에게 필요한 내용을 질문하고, 계약 여부를 결정하세요.",
  contract: {
    contractType: "전세",
    housingType: "빌라",
    deposit: "150,000,000원",
    contractPayment: "15,000,000원",
    balancePayment: "135,000,000원",
    contractPeriod: "2026.08.01. ~ 2028.07.31.",
    landlord: "김○○",
    tenant: "사용자",
    moveInDate: "2026.08.01.",
    specialClauses: [
      "임차인은 현재 시설 상태를 확인하고 계약한다.",
      "임대인은 임차인의 입주일까지 주택을 인도한다.",
      "임대차계약 종료 시 임차보증금은 후임 임차인의 보증금이 입금된 후 반환한다.",
      "임차인의 고의 또는 과실로 발생한 시설물 손상은 임차인이 원상복구한다.",
    ],
  },
  openingLine:
    "계약서 내용은 확인하셨죠? 다른 계약과 크게 다른 부분은 없습니다. 궁금한 내용이 없으시면 이제 서명 절차를 진행하겠습니다.",
  suggestedRevision:
    "임대인은 임대차계약 종료일에 임차목적물의 인도와 동시에 임차보증금을 반환한다. 후임 임차인의 계약 체결 또는 보증금 입금 여부는 반환 조건으로 하지 않는다.",
};

function includesAny(text: string, words: string[]) {
  return words.some((word) => text.includes(word));
}

export function classifyPracticeAnswer(answer: string): {
  speaker: PracticeSpeaker;
  response: string;
  observations: Partial<PracticeObservation>;
} {
  const normalized = answer.replace(/\s+/g, " ").trim();

  if (includesAny(normalized, ["삭제", "수정", "고쳐", "변경", "문구를 넣", "명확히 적"])) {
    return {
      speaker: "공인중개사",
      response:
        "임대인분이 이 조건을 원하고 계십니다. 다른 분도 계약을 고민하고 있어서 오래 기다려드리기는 어렵습니다.",
      observations: { requestedRevision: true },
    };
  }
  if (includesAny(normalized, ["안 구", "못 구", "구해지지", "없으면"])) {
    return {
      speaker: "임대인",
      response:
        "지금까지는 대부분 금방 구해졌습니다. 다음 임차인이 들어오면 받은 보증금으로 바로 돌려드릴 생각입니다.",
      observations: { askedNoSuccessor: true },
    };
  }
  if (includesAny(normalized, ["반환일", "종료일", "끝나는 날", "언제", "바로 돌려"])) {
    return {
      speaker: "임대인",
      response:
        "날짜를 확정해서 넣는 것은 조금 어렵습니다. 다음 임차인이 언제 들어올지 모르니까요.",
      observations: { askedReturnDate: true },
    };
  }
  if (includesAny(normalized, ["특약", "3번", "후임 임차인", "다음 세입자", "무슨 뜻", "어떤 뜻"])) {
    return {
      speaker: "공인중개사",
      response:
        "보증금을 돌려드리지 않는다는 뜻은 아니고요. 보통 다음 임차인이 들어오는 일정에 맞춰서 반환한다는 의미입니다.",
      observations: { askedMeaning: true },
    };
  }
  return {
    speaker: "공인중개사",
    response:
      "그러면 계약 내용에 동의하신 것으로 보고 서명을 진행하겠습니다. 서명 전에 더 확인하거나 요청할 내용이 있으면 말씀해 주세요.",
    observations: {},
  };
}

export const practiceService = {
  async getSigningScenario(): Promise<PracticeScenario> {
    return signingPracticeScenario;
  },
};
