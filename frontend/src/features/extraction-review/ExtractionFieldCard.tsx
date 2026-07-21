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

export function ExtractionFieldCard({
  view,
  draft,
  verification,
  onValueChange,
  onClauseChange,
  onConfirm,
}: {
  view: FieldViewModel;
  draft?: DraftValue;
  verification: VerificationStatus;
  onValueChange: (value: string) => void;
  onClauseChange: (values: string[]) => void;
  onConfirm: () => void;
}) {
  const values = Array.isArray(draft) ? draft : clauseValues(view.field);
  const hasDraftInput = Array.isArray(draft)
    ? draft.some((item) => item.trim().length > 0)
    : Boolean(draft?.trim());
  const failedWithoutInput = view.field.confidence === "실패" && !hasDraftInput;
  const hasEvidence = view.field.source_evidence.page !== null && view.field.source_evidence.text !== null;
  const isLongClauseList = ["main_clauses", "special_clauses"].includes(view.field.field_name);

  const editor = view.editor === "clause-list" ? (
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
          {view.field.issue_code ? issueStateLabels[view.field.issue_code] ?? view.field.confidence : view.field.confidence}
        </span>
        <span className={`verification verification--${verification}`}>{verificationLabels[verification]}</span>
      </div>
      {isLongClauseList ? (
        <details className="clause-details">
          <summary>{values.length > 0 ? `조항 ${values.length}개 펼쳐서 확인` : "조항을 펼쳐서 입력"}</summary>
          {editor}
        </details>
      ) : editor}
      {view.field.failure_reason && <p className="field-error">{view.field.failure_reason}</p>}
      {hasEvidence && <small>{`${view.field.source_evidence.page}쪽 · ${view.field.source_evidence.text}`}</small>}
      <button className="text-button" type="button" disabled={verification !== "unverified" || failedWithoutInput} onClick={onConfirm}>
        이 값 확인
      </button>
    </article>
  );
}
