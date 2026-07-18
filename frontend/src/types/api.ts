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

export interface UserDto {
  id: number;
  username: string;
  email: string;
}

export interface ContractSummaryDto {
  id: number;
  title: string;
  contract_type: ContractType | null;
  contract_stage: ContractStage | null;
  deposit_paid: boolean | null;
  signed: boolean | null;
  move_in_date: string | null;
  balance_payment_date: string | null;
  is_proxy_contract: boolean | null;
  registry_case_id: string | null;
  created_at: string;
}

export type ContractType = "전세" | "보증부 월세" | "일반 월세";
export type ContractStage = "계약금 입금 전" | "서명 전" | "계약 직후";

export interface SituationRequestDto {
  contract_type: ContractType;
  contract_stage: ContractStage;
  deposit_paid: boolean;
  signed: boolean;
  move_in_date: string | null;
  balance_payment_date: string | null;
  is_proxy_contract: boolean | null;
}

export type UploadDocumentType = "계약서" | "등기사항증명서" | "중개대상물 확인설명서";

export interface DocumentDto {
  id: number;
  doc_type: UploadDocumentType;
  filename: string;
  size_bytes: number;
  created_at: string;
}

export type FieldValue = string | number | boolean | string[] | null;
export type VerificationStatus = "unverified" | "confirmed" | "corrected";
export type ExtractionConfidence = "추출됨" | "불확실" | "실패";
export type DocumentType = "contract" | "registry";
export type SchemaVersion = "1.2.0";

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

export type GenerationMethod = "provider" | "template_fallback";

export interface GuidanceActionItemDto {
  item_key: string;
  text: string;
}

export interface RuleGuidanceDto {
  rule_id: string;
  explanation: string;
  questions: string[];
  signing_checklist: string[];
  post_contract_actions: string[];
  signing_checklist_items: GuidanceActionItemDto[];
  post_contract_action_items: GuidanceActionItemDto[];
  source_ids: string[];
  generation_method: GenerationMethod;
  provider_model: string | null;
  fallback_reason: string | null;
}

export interface GenerationResultDto {
  schema_version: SchemaVersion;
  analysis_run_id: string;
  items: RuleGuidanceDto[];
  guardrail_passed: true;
}

export type AsyncRunStatus = "pending" | "running" | "completed" | "failed";

export interface ExtractionStateDto {
  id: number;
  status: AsyncRunStatus;
  error: string | null;
  contract_doc: DocumentExtractionDto | null;
  registry_doc: DocumentExtractionDto | null;
  created_at: string;
}

export interface SnapshotResponseDto {
  input_snapshot_id: string;
  created_at: string;
}

export interface AnalysisRunSummaryDto {
  analysis_run_id: string;
  input_snapshot_id: string;
  status: AsyncRunStatus;
  created_at: string;
}

export interface AnalysisRunDetailDto extends AnalysisRunSummaryDto {
  error: string | null;
  result: AnalysisRunResultDto | null;
  generation_result: GenerationResultDto | null;
  generation_status: AsyncRunStatus | null;
  generation_error: string | null;
}

/** DTO와 분리된 화면 전용 타입. */
export interface FieldViewModel {
  key: string;
  document_type: DocumentType;
  label: string;
  formattedValue: string;
  field: ExtractedFieldDto;
}

export type ChecklistItemKind = "checklist" | "post_action";

export interface ChecklistItemStateDto {
  kind: ChecklistItemKind;
  item_key: string;
  done: boolean;
  updated_at: string;
}

export interface FeedbackCreateRequestDto {
  content: string;
  rating: number | null;
}

export interface FeedbackDto {
  id: number;
  contract_id: number;
  content: string;
  rating: number | null;
  created_at: string;
}