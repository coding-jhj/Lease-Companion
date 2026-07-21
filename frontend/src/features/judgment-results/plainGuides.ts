// 판정 항목의 쉬운 설명 + 금전 문제 안내. 리포트(PriorityGroups)와 8번 체크리스트가 공유한다.
// canonical 판정 id(J01~J12) 기준 정적 큐레이션 — 근거 없는 위험 단정이 아니라 "확인이 필요한 이유"를 쉽게 설명한다.
export interface PlainJudgmentGuide {
  explanation: string;
  financialImpact: string;
}

export const plainJudgmentGuides: Record<string, PlainJudgmentGuide> = {
  J01: {
    explanation: "계약서의 임대인이 등기사항증명서에 적힌 소유자와 같은 사람인지 확인하는 항목입니다. 다르면 대리 권한을 증명하는 서류가 필요합니다.",
    financialImpact: "권한이 확인되지 않은 상대에게 계약금이나 보증금을 보내면 돈을 돌려받는 과정이 복잡해질 수 있습니다.",
  },
  J02: {
    explanation: "계약서에 적힌 주택 주소와 등기사항증명서의 주소가 같은 집을 가리키는지 확인하는 항목입니다.",
    financialImpact: "주소가 다르면 다른 주택을 계약하거나 보증금 보호 절차에 필요한 정보를 잘못 준비할 수 있습니다.",
  },
  J03: {
    explanation: "주택 소유자가 여러 명이라면 계약에 필요한 공동소유자의 동의가 확인되는지 살펴보는 항목입니다.",
    financialImpact: "동의가 확인되지 않으면 계약 효력이나 보증금 반환 책임을 두고 분쟁이 생길 수 있습니다.",
  },
  J04: {
    explanation: "소유자가 아닌 대리인과 계약할 때 위임장과 인감증명서 등 권한 서류가 갖춰졌는지 확인하는 항목입니다.",
    financialImpact: "대리 권한이 없으면 지급한 계약금이나 보증금의 반환 책임을 두고 분쟁이 생길 수 있습니다.",
  },
  J05: {
    explanation: "계약금과 보증금을 받을 계좌의 예금주가 임대인 또는 적법한 계약 상대와 연결되는지 확인하는 항목입니다.",
    financialImpact: "관계없는 계좌로 송금하면 지급 사실을 증명하거나 돈을 돌려받기 어려워질 수 있습니다.",
  },
  J06: {
    explanation: "보증금·월세·계약금·잔금처럼 지급해야 할 금액이 빠짐없이 구체적으로 적혀 있는지 확인하는 항목입니다.",
    financialImpact: "금액이 빠지거나 모호하면 계약 후 예상하지 못한 추가 지급 요구나 정산 분쟁이 생길 수 있습니다.",
  },
  J07: {
    explanation: "계약서의 숫자 금액과 한글로 적은 금액이 서로 같은지 확인하는 항목입니다.",
    financialImpact: "두 표기가 다르면 실제 지급해야 할 금액을 두고 다툼이 생길 수 있습니다.",
  },
  J08: {
    explanation: "계약금·잔금 지급일, 입주일과 계약기간이 서로 모순 없이 이어지는지 확인하는 항목입니다.",
    financialImpact: "날짜가 맞지 않으면 잔금 지급, 입주와 이사 일정이 어긋나 추가 비용이나 분쟁이 생길 수 있습니다.",
  },
  J09: {
    explanation: "관리비 금액과 관리비에 포함되는 항목, 별도로 내야 하는 비용이 구체적인지 확인하는 항목입니다.",
    financialImpact: "내용이 불분명하면 계약 후 예상하지 못한 관리비나 별도 비용을 부담할 수 있습니다.",
  },
  J10: {
    explanation: "계약이 끝났을 때 보증금을 언제, 어떤 조건으로 돌려받는지가 명확한지 확인하는 항목입니다.",
    financialImpact: "반환 시점과 조건이 모호하면 보증금 반환이 늦어지거나 반환 책임을 두고 분쟁이 생길 수 있습니다.",
  },
  J11: {
    explanation: "주택의 수리와 퇴거 시 원상복구를 임대인과 임차인 중 누가 부담하는지 확인하는 항목입니다.",
    financialImpact: "책임 범위가 불분명하면 예상하지 못한 수리비나 원상복구 비용을 부담할 수 있습니다.",
  },
  J12: {
    explanation: "계약서 본문과 특약에 서로 다르거나 충돌하는 조건이 있는지 확인하는 항목입니다.",
    financialImpact: "충돌하는 문구를 그대로 두면 어떤 조건을 따라야 하는지 불분명해져 추가 비용이나 금전 책임 분쟁이 생길 수 있습니다.",
  },
};

const GENERIC_GUIDE: PlainJudgmentGuide = {
  explanation: "계약서와 관련 자료의 내용이 서로 맞고 필요한 조건이 구체적인지 확인하는 항목입니다.",
  financialImpact: "확인하지 않으면 예상하지 못한 비용이나 책임을 부담하거나 분쟁이 생길 수 있습니다.",
};

// 판정 id(J01~J12)로 가이드를 찾는다. 없으면(R 규칙·사실 플래그·미매핑) 일반 안내로 폴백한다.
export function plainGuideById(judgmentId: string | null | undefined): PlainJudgmentGuide {
  const guide = judgmentId ? plainJudgmentGuides[judgmentId] : undefined;
  return guide ?? GENERIC_GUIDE;
}
