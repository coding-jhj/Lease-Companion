const OFFICIAL_SOURCE_NAMES: Readonly<Record<string, string>> = {
  "SRC-STD-LEASE": "주택임대차 표준계약서",
  "SRC-HTA-LAW": "주택임대차보호법",
  "SRC-HTA-DECREE": "주택임대차보호법 시행령",
  "SRC-CIVIL-LEASE": "민법(임대차 관련)",
  "SRC-CONFIRM-FORM": "중개대상물 확인·설명서",
  "SRC-MOLIT-CHECKLIST": "안심 전세계약 체크리스트",
};

export function getOfficialSourceDisplayName(sourceId: string): string {
  return OFFICIAL_SOURCE_NAMES[sourceId] ?? "공식 자료";
}

export function getOfficialSourceDisplayNames(sourceIds: readonly string[]): string[] {
  return [...new Set(sourceIds.map(getOfficialSourceDisplayName))];
}
