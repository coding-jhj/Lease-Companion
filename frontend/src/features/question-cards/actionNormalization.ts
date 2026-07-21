import type { ChecklistItemKind } from "../../types/api";

export interface NormalizedAction {
  identity: string;
  kind: ChecklistItemKind;
  text: string;
}

const CANONICAL_ACTIONS: Array<{
  identity: string;
  kind: ChecklistItemKind;
  pattern: RegExp;
  text: string;
}> = [
  { identity: "lease-report", kind: "post_action", pattern: /임대차(?:계약)?신고/, text: "신고 대상 여부를 확인하고, 대상이면 계약 체결일부터 30일 이내에 주택 임대차 계약 신고를 완료한 뒤 처리 결과를 보관하세요." },
  { identity: "move-in-protection", kind: "post_action", pattern: /전입신고|확정일자/, text: "실제 입주 후 전입신고·확정일자 등 권리 확보 절차를 완료하고 처리 결과를 확인하세요." },
  { identity: "ownership-authority", kind: "checklist", pattern: /갑구.*소유자|소유자.*갑구|등기상소유자|소유자와계약자|소유자와계약상대|계약권한/, text: "최신 등기사항증명서의 소유자와 계약 상대가 일치하는지 확인하고, 다르면 계약 권한 서류를 확인하세요." },
  { identity: "registry-rights", kind: "checklist", pattern: /최신.*등기|등기사항증명서.*발급|갑구와을구|갑구.*을구|소유권제한|권리제한/, text: "계약·잔금 직전 최신 등기사항증명서를 발급받아 갑구·을구의 소유권과 권리제한을 확인하세요." },
  { identity: "senior-claims", kind: "checklist", pattern: /선순위.*(?:근저당|권리|채권|금액)|근저당.*선순위/, text: "선순위 권리의 종류와 채권최고액·실채무액을 확인하고 관련 자료를 보관하세요." },
  { identity: "tax-arrears", kind: "checklist", pattern: /국세|지방세|납세증명|완납증명/, text: "계약 전에 적법한 절차로 임대인의 국세·지방세 관련 자료를 확인하고 보관하세요." },
  { identity: "account-holder", kind: "checklist", pattern: /예금주|계좌명의|임대인명의의계좌/, text: "입금 전에 계좌 명의와 계약 상대가 일치하는지 확인하세요." },
  { identity: "property-address", kind: "checklist", pattern: /계약서주소.*등기|등기상주소|목적물주소/, text: "계약서의 목적물 주소와 등기사항증명서의 주소가 일치하는지 확인하세요." },
  { identity: "market-price", kind: "checklist", pattern: /실거래|시세|전세가/, text: "공식 실거래 자료에서 동일·유사 주택의 가격을 확인하고 기준일과 비교 조건을 기록하세요." },
  { identity: "broker-disclosure", kind: "checklist", pattern: /중개대상물.*(?:확인|설명)|확인.?설명서/, text: "서명 전에 중개대상물 확인·설명서의 내용을 확인하고 사본을 교부받으세요." },
];

export function normalizeAction(text: string, fallbackKind: ChecklistItemKind): NormalizedAction {
  const trimmed = text.trim();
  const compact = trimmed.replace(/\s+/g, "");
  const canonical = CANONICAL_ACTIONS.find((candidate) => candidate.pattern.test(compact));
  if (canonical) return { identity: canonical.identity, kind: canonical.kind, text: canonical.text };
  return { identity: compact, kind: fallbackKind, text: trimmed };
}
