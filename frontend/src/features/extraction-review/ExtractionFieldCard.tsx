import { clauseValues } from "./viewModel";
import type { FieldViewModel, VerificationStatus } from "../../types/api";

type DraftValue = string | string[];

const verificationLabels: Record<VerificationStatus, string> = {
  unverified: "미확인",
  confirmed: "확인됨",
  corrected: "수정됨",
};

// issue_code가 있으면 칩 문구를 정확한 상태로 교체한다(요소 추가 없이 confidence 칩 텍스트만 바꿈).
// 색은 confidence 클래스로 유지 — 미기재/판독 실패를 같은 "실패"로 뭉뚱그리지 않는다.
const issueStateLabels: Record<string, string> = {
  not_stated: "미기재",
  unreadable: "판독 실패",
  ambiguous: "모호",
  parse_failed: "형식 오류",
  not_applicable: "적용 제외",
};

const troubleshootingLocations: Record<string, string> = {
  special_clauses: "계약서의 [특약사항] 아래 글머리표 문장을 확인하세요.",
  end_date: "계약서 제2조(임대차기간)의 ‘~까지로 한다’ 날짜를 확인하세요.",
  start_date: "계약서 제2조(임대차기간)의 인도일 또는 시작일을 확인하세요.",
  bank_name: "제1조 차임·월세 항목의 입금계좌 괄호 안 은행명을 확인하세요.",
  account_number: "제1조 차임·월세 항목의 입금계좌 번호를 확인하세요.",
  account_holder: "입금계좌 옆 예금주 표기 또는 계약 상대 명의를 확인하세요.",
  contract_payment: "제1조의 계약금 금액을 확인하세요.",
  contract_payment_date: "제1조의 계약금 지급 문구와 계약 체결일을 확인하세요.",
  balance_payment: "제1조의 잔금 금액을 확인하세요.",
  balance_payment_date: "제1조의 잔금 지급일을 확인하세요.",
  owner_shares: "등기사항증명서 갑구의 현재 소유자와 지분 표시를 확인하세요.",
  senior_claim_amount: "등기사항증명서 을구의 권리 종류와 채권최고액을 확인하세요.",
};

export function ExtractionFieldCard({
  view,
  draft,
  verification,
  reviewed,
  allowEmptyConfirmation = false,
  onValueChange,
  onClauseChange,
  onConfirm,
}: {
  view: FieldViewModel;
  draft?: DraftValue;
  verification: VerificationStatus;
  reviewed: boolean;
  allowEmptyConfirmation?: boolean;
  onValueChange: (value: string) => void;
  onClauseChange: (values: string[]) => void;
  onConfirm: () => void;
}) {
  const values = Array.isArray(draft) ? draft : clauseValues(view.field);
  const hasDraftInput = Array.isArray(draft)
    ? draft.some((item) => item.trim().length > 0)
    : Boolean(draft?.trim());
  const canConfirmMissing = allowEmptyConfirmation
    || view.field.issue_code === "not_stated"
    || view.field.issue_code === "not_applicable";
  const failedWithoutInput = view.field.confidence === "실패" && !hasDraftInput && !canConfirmMissing;
  const hasEvidence = view.field.source_evidence.page !== null && view.field.source_evidence.text !== null;
  const isLongClauseList = ["main_clauses", "special_clauses"].includes(view.field.field_name);
  const selectedChoice = typeof draft === "string" ? draft : "";
  const confirmLabel = allowEmptyConfirmation && !hasDraftInput
    ? "확인할 수 없음으로 저장"
    : view.field.issue_code === "not_stated" && !hasDraftInput ? "직접 확인" : "이 값 확인";
  const showInlineDirectConfirm = confirmLabel === "직접 확인" && view.editor === "scalar";
  const showTroubleshooting = ["unreadable", "parse_failed"].includes(view.field.issue_code ?? "")
    || (view.field.confidence === "실패" && !canConfirmMissing);
  const troubleshootingLocation = troubleshootingLocations[view.field.field_name]
    ?? "원본 문서에서 해당 항목의 제목과 기재란을 확인하세요.";

  const choiceEditor = (
    options: Array<{ value: string; label: string }>,
  ) => (
    <fieldset className="field-choice-group">
      <legend className="sr-only">{view.label}</legend>
      {options.map((option) => (
        <label className="field-choice" key={option.value}>
          <input
            type="radio"
            name={`${view.key}-choice`}
            value={option.value}
            checked={selectedChoice === option.value}
            onChange={(event) => onValueChange(event.target.value)}
          />
          <span>{option.label}</span>
        </label>
      ))}
    </fieldset>
  );

  const editor = view.editor === "boolean-choice" ? choiceEditor([
    { value: "true", label: "가입 가능" },
    { value: "false", label: "가입 불가" },
  ]) : view.editor === "authority-choice" ? choiceEditor([
    { value: "owner_direct", label: "등기 소유자와 직접 계약" },
    { value: "sublease_documents", label: "소유자 동의·전대 권한서류 확인" },
    { value: "not_confirmed", label: "아직 확인하지 못함" },
  ]) : view.editor === "clause-list" ? (
    <div className="clause-list-editor">
      {(values.length > 0 ? values : [""]).map((value, index) => (
        <div className="clause-list-editor__item" key={`${view.key}:${index}`}>
          <label>
            <span className="sr-only">{`${view.label} ${index + 1} 값`}</span>
            <input
              aria-label={`${view.label} ${index + 1} 값`}
              value={value}
              placeholder={view.field.confidence === "실패" ? "조항을 직접 입력해 주세요" : undefined}
              onChange={(event) => {
                const next = [...values];
                next[index] = event.target.value;
                onClauseChange(next);
              }}
            />
          </label>
          <button
            className="text-button"
            type="button"
            aria-label={`${view.label} ${index + 1} 삭제`}
            onClick={() => onClauseChange(values.filter((_, itemIndex) => itemIndex !== index))}
          >
            이 조항 삭제
          </button>
        </div>
      ))}
      <button className="secondary" type="button" onClick={() => onClauseChange([...values, ""])}>
        조항 추가
      </button>
    </div>
  ) : (
    <label>
      <span className="sr-only">{view.label} 값</span>
      <input
        aria-label={`${view.label} 값`}
        value={typeof draft === "string" ? draft : view.formattedValue}
        placeholder={view.field.confidence === "실패" ? "직접 입력해 주세요" : undefined}
        onChange={(event) => onValueChange(event.target.value)}
      />
    </label>
  );

  return (
    <article className="field-card">
      <div className="field-card__meta">
        <strong>{view.label}</strong>
        <span className={`confidence confidence--${view.field.confidence}`}>
          {["guarantee_eligibility_confirmed", "lessor_sublease_authority_confirmed"].includes(view.field.field_name)
            ? "직접 확인"
            : view.field.issue_code ? issueStateLabels[view.field.issue_code] ?? view.field.confidence : view.field.confidence}
        </span>
        <span className={`verification verification--${verification}`}>{verificationLabels[verification]}</span>
      </div>
      {isLongClauseList ? (
        <details className="clause-details">
          <summary>{values.length > 0 ? `조항 ${values.length}개 펼쳐서 확인` : "조항을 펼쳐서 입력"}</summary>
          {editor}
        </details>
      ) : showInlineDirectConfirm ? (
        <div className="field-direct-confirm-row">
          {editor}
          <button
            aria-label={`${view.label} 직접 확인`}
            className="secondary"
            type="button"
            disabled={reviewed}
            onClick={onConfirm}
          >
            직접 확인
          </button>
        </div>
      ) : editor}
      {view.field.failure_reason && <p className="field-error">{view.field.failure_reason}</p>}
      {showTroubleshooting && (
        <details className="field-troubleshooting">
          <summary>판독 실패 해결 방법</summary>
          <ol>
            <li>{troubleshootingLocation}</li>
            <li>원문에서 값이 확인되면 위 입력칸에 그대로 입력하고 <strong>이 값 확인</strong>을 누르세요.</li>
            <li>원문도 흐리거나 잘려 있다면 해당 페이지가 선명하게 보이는 PDF·이미지를 다시 업로드해 추출하세요.</li>
          </ol>
          <p>직접 입력한 값은 자동 추출값이 아니라 사용자가 확인한 수정값으로 저장됩니다.</p>
        </details>
      )}
      {view.guidance && <small>{view.guidance}</small>}
      {hasEvidence && <small>{`${view.field.source_evidence.page}쪽 · ${view.field.source_evidence.text}`}</small>}
      {!showInlineDirectConfirm && (
        <button
          aria-label={`${view.label} ${confirmLabel}`}
          className="text-button"
          type="button"
          disabled={reviewed || failedWithoutInput}
          onClick={onConfirm}
        >
          {confirmLabel}
        </button>
      )}
    </article>
  );
}
