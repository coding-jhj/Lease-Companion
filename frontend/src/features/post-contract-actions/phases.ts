// 계약 후 행동 표시 순서. 판정은 바꾸지 않는다.
export const POST_ACTION_PHASES = [
  "계약 체결 직후",
  "잔금 지급 전",
  "잔금 지급 시",
  "잔금·입주 후",
] as const;

export type PostActionPhase = (typeof POST_ACTION_PHASES)[number];

export interface StandardPostAction {
  id: string;
  phase: PostActionPhase;
  text: string;
  method: string;
  pattern: RegExp;
  sources: Array<{ name: string; url: string }>;
}

const MOLIT_SOURCE = {
  name: "국토교통부 3·3·3 안심계약 체크리스트",
  url: "https://www.molit.go.kr/USR/NEWS/m_71/dtl.jsp?id=95091157",
};
const HTA_SOURCE = {
  name: "주택임대차보호법 제3조·제3조의2·제3조의6",
  url: "https://www.law.go.kr/LSW/lsInfoP.do?lsiSeq=276291",
};

// repo의 official_verified 자료(SRC-MOLIT-CHECKLIST·SRC-HTA-LAW)를 화면용으로 정리한 고정 안내.
// 규칙 결과에서 같은 행동이 오면 pattern으로 합치고, 빠진 행동만 보충 안내로 표시한다.
export const STANDARD_POST_ACTIONS: StandardPostAction[] = [
  {
    id: "lease-report",
    phase: "계약 체결 직후",
    text: "주택 임대차 계약 신고 대상인지 확인하고, 대상이면 신고하세요.",
    method: "계약서를 준비해 주민센터 또는 부동산거래관리시스템에서 신고 대상·기한·처리 결과를 확인하세요.",
    pattern: /임대차계약.{0,4}신고|임대차.{0,2}신고|주택 임대차 계약 신고/,
    sources: [MOLIT_SOURCE],
  },
  {
    id: "fixed-date",
    phase: "계약 체결 직후",
    text: "확정일자를 받았는지 확인하세요.",
    method: "임대차 신고로 확정일자가 부여됐는지 먼저 확인하고, 아니라면 주민센터·등기소 등 공식 창구에서 절차를 확인하세요.",
    pattern: /확정일자/,
    sources: [MOLIT_SOURCE, HTA_SOURCE],
  },
  {
    id: "registry-before-balance",
    phase: "잔금 지급 전",
    text: "잔금 송금 직전에 최신 등기사항증명서를 다시 확인하세요.",
    method: "새 등기사항증명서를 발급해 갑구·을구의 소유자와 근저당·압류·소유권 변동을 계약 때 자료와 대조하세요.",
    pattern: /잔금.{0,12}(?:전|직전).{0,20}등기|등기사항증명서.{0,15}(?:다시|재확인|재발급)/,
    sources: [MOLIT_SOURCE],
  },
  {
    id: "special-clause-performance",
    phase: "잔금 지급 전",
    text: "도배·장판·수리 등 임대인이 약속한 특약이 이행됐는지 확인하세요.",
    method: "계약서 특약과 현장 상태를 대조하고, 미이행 내용은 잔금 지급 전에 임대인과 서면으로 확인하세요.",
    pattern: /특약.{0,10}이행|도배|장판|수리.{0,10}(?:이행|확인)/,
    sources: [MOLIT_SOURCE],
  },
  {
    id: "landlord-account",
    phase: "잔금 지급 시",
    text: "임대인 본인 명의 계좌인지 확인한 뒤 잔금을 송금하세요.",
    method: "계약서의 임대인 이름과 계좌 예금주를 대조하고, 다르면 송금 전에 사유와 권한 자료를 확인하세요.",
    pattern: /임대인.{0,8}(?:명의|계좌)|계좌.{0,8}명의/,
    sources: [MOLIT_SOURCE],
  },
  {
    id: "transfer-records",
    phase: "잔금 지급 시",
    text: "잔금 이체내역과 영수증을 보관하세요.",
    method: "수취인·금액·송금 일시가 보이는 이체확인증과 영수증을 계약서 사본과 함께 보관하세요.",
    pattern: /잔금.{0,10}이체내역|이체내역.{0,10}잔금|영수증/,
    sources: [MOLIT_SOURCE],
  },
  {
    id: "housing-delivery",
    phase: "잔금 지급 시",
    text: "기존 세입자 퇴거와 주택·열쇠 인도 상태를 확인하세요.",
    method: "기존 세입자 퇴거, 빈집 상태, 열쇠·도어락 인계를 현장에서 확인하고 사진이나 인수 기록을 남기세요.",
    pattern: /퇴거|주택.{0,8}인도|인도 상태|열쇠|도어락/,
    sources: [MOLIT_SOURCE],
  },
  {
    id: "move-in-report",
    phase: "잔금·입주 후",
    text: "주택을 인도받은 뒤 전입신고를 진행하세요.",
    method: "실제 입주·인도 상태를 확인한 뒤 주민센터 또는 정부24에서 전입신고 처리 결과를 확인하세요.",
    pattern: /전입신고/,
    sources: [MOLIT_SOURCE, HTA_SOURCE],
  },
  {
    id: "priority-requirements",
    phase: "잔금·입주 후",
    text: "주택 인도·전입신고·확정일자 요건을 모두 갖췄는지 확인하세요.",
    method: "주택 인도와 전입신고를 마친 시점, 계약서 확정일자를 각각 확인하고 증빙을 함께 보관하세요.",
    pattern: /우선변제|대항력|권리 확보 절차|주택 인도.{0,20}전입신고/,
    sources: [HTA_SOURCE],
  },
  {
    id: "return-guarantee",
    phase: "잔금·입주 후",
    text: "보증기관 공식 채널에서 반환보증 가입 요건과 결과를 확인하세요.",
    method: "계약 조건과 신청 기한을 보증기관 공식 채널에서 확인하고, 신청·심사 결과를 보관하세요.",
    pattern: /반환보증|보증기관.{0,12}(?:가입|심사)|보증 가입/,
    sources: [MOLIT_SOURCE],
  },
  {
    id: "registry-after-move-in",
    phase: "잔금·입주 후",
    text: "전입신고 후 약 1주일 뒤 등기사항증명서를 다시 확인하세요.",
    method: "새 등기사항증명서를 발급해 전입신고 전후 추가 담보권·압류·소유권 변동이 없는지 확인하세요.",
    pattern: /전입신고.{0,16}(?:1주일|일주일).{0,20}등기|입주.{0,12}후.{0,20}등기.{0,10}(?:다시|재확인)/,
    sources: [MOLIT_SOURCE],
  },
];

export function standardPostActionFor(text: string): StandardPostAction | null {
  return STANDARD_POST_ACTIONS.find((action) => action.pattern.test(text)) ?? null;
}

const PHASE_PATTERNS: Array<{ phase: PostActionPhase; pattern: RegExp }> = [
  { phase: "잔금 지급 시", pattern: /잔금.{0,10}(?:지급|송금|이체|대면)|계좌\s*명의|이체내역|영수증|열쇠|인도받/ },
  { phase: "잔금 지급 전", pattern: /잔금\s*(?:지급\s*)?전|송금\s*(?:직)?전|권리\s*변동|등기부.{0,6}재확인|다시\s*확인|특약.{0,6}이행|퇴거/ },
  { phase: "잔금·입주 후", pattern: /전입신고|확정일자|대항력|우선변제|반환보증|보증\s*가입|입주\s*후/ },
  { phase: "계약 체결 직후", pattern: /신고|해제|해지|보관/ },
];

export function phaseForAction(text: string): PostActionPhase {
  const standard = standardPostActionFor(text);
  if (standard) return standard.phase;
  const compact = text.replace(/\s+/g, " ");
  return PHASE_PATTERNS.find((candidate) => candidate.pattern.test(compact))?.phase
    ?? "계약 체결 직후";
}
