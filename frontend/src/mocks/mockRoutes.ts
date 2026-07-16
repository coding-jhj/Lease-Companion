/**
 * OpenAPI에 아직 없는 MVP 흐름의 MSW 전용 경로다.
 * Backend 계약이 확정되면 생성 타입과 실제 경로로 한 번에 교체한다.
 */
export const mockOnlyMvpRoutes = {
  extraction: (contractId: number) => `/__mock__/contracts/${contractId}/extraction`,
  corrections: (contractId: number) => `/__mock__/contracts/${contractId}/corrections`,
  confirmation: (contractId: number) => `/__mock__/contracts/${contractId}/confirmation`,
  analyses: (contractId: number) => `/__mock__/contracts/${contractId}/analyses`,
  analysisResult: (contractId: number) => `/__mock__/contracts/${contractId}/analysis-result`,
} as const;

export const CASE_001_CONTRACT_ID = 1001;
