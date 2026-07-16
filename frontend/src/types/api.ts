export interface ApiValidationDetail {
  loc: (string | number)[];
  msg: string;
  type: string;
}

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    details?: ApiValidationDetail[];
  };
}

export interface AuthResponse {
  accessToken: string;
  user: { id: string; name: string };
}

export interface ContractSummary {
  contractId: string;
  title: string;
  stage: string;
  updatedAt: string;
}

export type VerificationStatus = "unverified" | "confirmed" | "corrected";
export type ExtractionConfidence = "추출됨" | "불확실" | "실패";

export interface ExtractedField {
  fieldName: string;
  label: string;
  extractedValue: string | null;
  userCorrectedValue: string | null;
  verificationStatus: VerificationStatus;
  confidence: ExtractionConfidence;
  evidence: { page: number | null; text: string | null };
}

export interface ReportItem {
  judgmentId: string;
  title: string;
  status: string;
  urgency: string;
  priority: "반드시 확인" | "확인 권장" | "일반 확인";
  explanation: string;
}

export interface ChecklistItem {
  id: string;
  label: string;
  completed: boolean;
}
