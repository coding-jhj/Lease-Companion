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
  // 대시보드 행동 상태: none(미행동)/in_progress(행동중)/done(행동 완료).
  action_status?: "none" | "in_progress" | "done";
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

export interface ContractContextDto extends SituationRequestDto {
  schema_version: SchemaVersion;
  contract_id: number;
}

export type UploadDocumentType = "계약서" | "등기사항증명서" | "중개대상물 확인설명서";

export interface DocumentDto {
  id: number;
  doc_type: UploadDocumentType;
  filename: string;
  size_bytes: number;
  created_at: string;
}

export type FieldValue = string | number | boolean | string[] | Record<string, string> | null;
export type VerificationStatus = "unverified" | "confirmed" | "corrected";
export type ExtractionConfidence = "추출됨" | "불확실" | "실패";
export type FieldIssueCode = "not_stated" | "unreadable" | "ambiguous" | "parse_failed" | "not_applicable";
export type DocumentType = "contract" | "registry";
export type SchemaVersion = "1.8.0" | "1.9.0";

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
  issue_code: FieldIssueCode | null;
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
  contract_context: ContractContextDto;
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
  // 참고용 공식자료 전체 원문. summary(이번 판정 관련 검색 발췌)와 구분해 표시한다.
  source_text?: string | null;
  source_url: string | null;
  // 이 근거를 회수한 검색 방식(관찰용). 정적 카탈로그 항목은 null.
  retrieval_method?: "bm25" | "vector" | "hybrid" | "rerank" | null;
}

export type DamagePatternStatus =
  | "관련 확인 신호 있음"
  | "제출 자료에서 관련 신호 미확인"
  | "자료 부족으로 확인 불가"
  | "예방 확인 필요";

export interface ReferenceCaseDto {
  reference_case_id: string;
  title: string;
  publisher: string;
  published_at: string | null;
  source_url: string;
  summary: string;
  verification_scope: string;
}

export interface DamagePatternComparisonDto {
  pattern_id: string;
  pattern_name: string;
  status: DamagePatternStatus;
  reason: string;
  related_rule_ids: string[];
  related_judgment_ids: string[];
  limitations: string;
  official_sources: OfficialSourceDto[];
  reference_cases: ReferenceCaseDto[];
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
  triggers_actions: boolean;
}

export interface JudgmentResultDto {
  judgment_id: `J${string}`;
  judgment_name: string;
  status: RuleStatus;
  urgency: Urgency;
  triggers_actions: boolean;
  reason: string;
  question: string | null;
  recommended_actions: string[];
  evidence_sources: OfficialSourceDto[];
  limitations: string;
}

export interface AnalysisRunResultDto {
  schema_version: SchemaVersion;
  analysis_run_id: string;
  input_snapshot_id: string;
  contract_id: number;
  case_id: string | null;
  results: RuleResultDto[];
  judgments: JudgmentResultDto[];
  damage_patterns?: DamagePatternComparisonDto[];
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
  request_templates?: string[];
  signing_checklist: string[];
  post_contract_actions: string[];
  signing_checklist_items: GuidanceActionItemDto[];
  post_contract_action_items: GuidanceActionItemDto[];
  source_ids: string[];
  generation_method: GenerationMethod;
  provider_model: string | null;
  fallback_reason: string | null;
}

export interface JudgmentGuidanceDto {
  judgment_id: string;
  explanation: string;
  questions: string[];
  request_templates?: string[];
  signing_checklist: string[];
  post_contract_actions: string[];
  signing_checklist_items: GuidanceActionItemDto[];
  post_contract_action_items: GuidanceActionItemDto[];
  source_ids: string[];
  generation_method: GenerationMethod;
  provider_model: string | null;
  fallback_reason: string | null;
}

export interface StageGuidanceDto {
  contract_context: ContractContextDto;
  before_deposit_questions: string[];
  signing_checklist: string[];
  post_contract_actions: string[];
  record_retention: string[];
  before_contract_actions?: string[];
  during_contract_actions?: string[];
  closing_day_actions?: string[];
  after_contract_actions?: string[];
}

export interface GenerationResultDto {
  schema_version: SchemaVersion;
  analysis_run_id: string;
  // 과거 저장 결과(v1) 읽기 호환 + 신규 생성 결과(v2).
  prompt_version: "v1" | "v2";
  items: RuleGuidanceDto[];
  judgment_items: JudgmentGuidanceDto[];
  stage_guidance: StageGuidanceDto;
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
  editor: "scalar" | "clause-list" | "boolean-choice" | "authority-choice";
  guidance: string | null;
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
