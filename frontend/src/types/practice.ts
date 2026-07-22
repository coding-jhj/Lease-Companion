export type PracticePhase = "intro" | "contract" | "dialogue" | "action" | "debrief";

export type PracticeSpeaker = "공인중개사" | "임대인" | "사용자";

export interface PracticeContractSummary {
  contractType: string;
  housingType: string;
  deposit: string;
  contractPayment: string;
  balancePayment: string;
  contractPeriod: string;
  landlord: string;
  tenant: string;
  moveInDate: string;
  specialClauses: string[];
}

export interface PracticeScenario {
  scenarioId: string;
  title: string;
  labels: string[];
  situation: string;
  instruction: string;
  contract: PracticeContractSummary;
  openingLine: string;
  suggestedRevision: string;
}

export interface PracticeMessage {
  id: string;
  speaker: PracticeSpeaker;
  text: string;
}

export interface PracticeObservation {
  askedMeaning: boolean;
  askedNoSuccessor: boolean;
  askedReturnDate: boolean;
  requestedRevision: boolean;
}

export type PracticeFinalAction =
  | "현재 조건으로 계약 체결"
  | "특약 수정을 다시 요구"
  | "계약 보류";
