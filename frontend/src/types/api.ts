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
  access_token: string;
  token_type: "bearer";
}

export interface ContractSummaryDto {
  contract_id: number;
  title: string;
  stage: string;
  updated_at: string;
}

export type FieldValue = string | number | boolean | string[] | null;
export type VerificationStatus = "unverified" | "confirmed" | "corrected";
export type ExtractionConfidence = "추출됨" | "불확실" | "실패";
export type DocumentType = "contract" | "registry";
export type SchemaVersion = "1.1.0";

export interface SourceEvidenceDto {
  page: number | null;
  text: string | null;
}

/** Canonical Pydantic ExtractedField의 wire DTO. 화면 문구를 넣지 않는다. */
export interface ExtractedFieldDto {
  field_name: string;
  extracted_value: FieldValue;
  normalized_value: FieldValue;
  user_corrected_value: FieldValue;
  verification_status: VerificationStatus;
  confidence: ExtractionConfidence;
  source_evidence: SourceEvidenceDto;
  failure_reason: string | null;
}

export interface DocumentExtractionDto {
  schema_version: SchemaVersion;
  document_id: string;
  document_type: DocumentType;
  fields: Record<string, ExtractedFieldDto>;
  warnings: string[];
}

export interface FieldCorrectionDto {
  document_type: DocumentType;
  field_name: string;
  corrected_value: Exclude<FieldValue, null>;
}

export interface CorrectionRequestDto {
  schema_version: SchemaVersion;
  contract_id: number;
  corrections: FieldCorrectionDto[];
}

export interface InputSnapshotDto {
  schema_version: SchemaVersion;
  input_snapshot_id: string;
  contract_id: number;
  case_id: string | null;
  confirmed_fields: Record<DocumentType, Record<string, ExtractedFieldDto>>;
  confirmed_at: string;
}

export type RuleStatus =
  | "일치"
  | "불일치"
  | "명확"
  | "불명확"
  | "미기재"
  | "상충 가능"
  | "확인 필요"
  | "확인 불가"
  | "적용 제외";

export type Urgency = "즉시 확인" | "계약 전 확인" | "계약 직후 조치" | "참고" | "분석 불가";

export interface OfficialSourceDto {
  source_id: string;
  title: string;
  institution: string;
  summary: string | null;
  source_url: string | null;
}

export interface RuleResultDto {
  rule_id: string;
  rule_name: string;
  judgment_id: string | null;
  status: RuleStatus;
  urgency: Urgency;
  reason: string;
  question: string | null;
  recommended_actions: string[];
  evidence_sources: OfficialSourceDto[];
  limitations: string;
  completed: boolean;
}

export interface AnalysisRunResultDto {
  schema_version: SchemaVersion;
  analysis_run_id: string;
  input_snapshot_id: string;
  contract_id: number;
  case_id: string | null;
  results: RuleResultDto[];
}

/** DTO와 분리된 화면 전용 타입. */
export interface FieldViewModel {
  key: string;
  document_type: DocumentType;
  label: string;
  formattedValue: string;
  field: ExtractedFieldDto;
}

export interface ChecklistItem {
  id: string;
  label: string;
  completed: boolean;
}
