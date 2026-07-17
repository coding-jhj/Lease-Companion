import { CASE_001_CONTRACT_ID } from "../mocks/mockRoutes";

export function contractIdFromRoute(value?: string): number {
  const contractId = Number(value ?? CASE_001_CONTRACT_ID);
  if (!Number.isSafeInteger(contractId) || contractId <= 0) {
    throw new Error("contract_id는 양의 정수여야 합니다.");
  }

  return contractId;
}
