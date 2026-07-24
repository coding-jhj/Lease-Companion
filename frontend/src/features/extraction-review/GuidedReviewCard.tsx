import { useEffect, useId, useState } from "react";

import type { ReviewQueueItem } from "./reviewQueue";
import { splitClauseText } from "./viewModel";

type CannotVerifyReason = "not_stated" | "unreadable" | "unknown_location";

// 자주 나오는 특약 유형의 쉬운 뜻(참고용). 매칭 안 되면 표시하지 않는다(임의 생성 금지).
const CLAUSE_PLAIN_HINTS: Array<{ match: RegExp; text: string }> = [
  { match: /전입신고|확정일자/, text: "전입신고와 확정일자로 보증금 우선순위(대항력·우선변제)를 확보하려는 조건입니다." },
  { match: /저당권|담보권|근저당/, text: "잔금 다음 날까지 집에 새 빚(저당 등)을 걸지 못하게 해 보증금을 지키려는 조항입니다." },
  { match: /선순위|국세|지방세|체납|미납/, text: "숨은 앞순위 세입자나 체납 세금이 크면 계약을 해지할 수 있다는 뜻입니다." },
  { match: /분쟁조정|조정위원회|조정을 신청/, text: "다툼이 생기면 소송 전에 조정 절차를 먼저 신청하기로 한 약속입니다." },
  { match: /재건축|철거|재개발/, text: "집을 헐거나 다시 지을 계획에 대한 내용입니다. 거주 기간에 영향을 줄 수 있어 확인이 필요합니다." },
  { match: /상세주소/, text: "상세주소가 없을 때 임차인이 주소 부여를 신청하는 데 대한 소유자 동의 내용입니다." },
  { match: /수선|수리비용|수리 및 비용|구조변경/, text: "집의 수리·고장 책임을 누가 지는지에 대한 내용입니다. 보통 큰 수리는 임대인, 소모품·간단 수리는 임차인 부담입니다." },
  { match: /원래의 상태로 복구|원상회복|원상복구/, text: "계약이 끝나면 집을 원래 상태로 되돌려 넘기고, 그와 동시에 보증금을 돌려받는다는 뜻입니다." },
];

function clausePlainHint(text: string): string | null {
  return CLAUSE_PLAIN_HINTS.find((hint) => hint.match.test(text))?.text ?? null;
}

export interface GuidedReviewCardProps {
  item: ReviewQueueItem;
  draftValue: string | string[] | undefined;
  busy: boolean;
  onConfirm: () => void;
  onChange: (value: string | string[]) => void;
  onCannotVerify: (reason: CannotVerifyReason) => void;
}

function initialValue(item: ReviewQueueItem, draftValue: string | string[] | undefined): string {
  if (Array.isArray(draftValue)) return draftValue.join("\n");
  if (typeof draftValue === "string") return draftValue;
  if (Array.isArray(item.view.field.user_corrected_value)) {
    return item.view.field.user_corrected_value.join("\n");
  }
  if (Array.isArray(item.view.field.normalized_value)) {
    return item.view.field.normalized_value.join("\n");
  }
  if (Array.isArray(item.view.field.extracted_value)) {
    return item.view.field.extracted_value.join("\n");
  }
  return item.view.formattedValue;
}

function isMultiline(item: ReviewQueueItem, draftValue: string | string[] | undefined): boolean {
  return item.fieldName === "special_clauses"
    || Array.isArray(draftValue)
    || Array.isArray(item.view.field.user_corrected_value)
    || Array.isArray(item.view.field.normalized_value)
    || Array.isArray(item.view.field.extracted_value);
}

export function GuidedReviewCard({
  item,
  draftValue,
  busy,
  onConfirm,
  onChange,
  onCannotVerify,
}: GuidedReviewCardProps) {
  const originalValue = initialValue(item, draftValue);
  const multiline = isMultiline(item, draftValue);
  const isClauseField = multiline
    || item.fieldName === "deposit_return_clause"
    || item.fieldName === "repair_responsibility_clause";
  const generatedId = useId();
  const correctionId = `${generatedId}-correction`;
  const cannotVerifyName = `${generatedId}-cannot-verify`;
  const [mode, setMode] = useState<"view" | "editing" | "cannot-verify">("view");
  const [editedValue, setEditedValue] = useState(originalValue);
  const [showEmptyError, setShowEmptyError] = useState(false);

  useEffect(() => {
    setMode("view");
    setEditedValue(originalValue);
    setShowEmptyError(false);
  }, [item.key, originalValue]);

  const startEditing = () => {
    setEditedValue(originalValue);
    setShowEmptyError(false);
    setMode("editing");
  };

  const cancelEditing = () => {
    setEditedValue(originalValue);
    setShowEmptyError(false);
    setMode("view");
  };

  const saveChange = () => {
    if (!editedValue.trim()) {
      setShowEmptyError(true);
      return;
    }

    onChange(multiline
      ? editedValue.split("\n").map((line) => line.trim()).filter(Boolean)
      : editedValue);
  };

  return (
    <article className="guided-review-card">
      <h2>{item.title}</h2>
      <p>{item.prompt}</p>
      <section aria-label="문서에서 읽은 내용">
        <h3>문서에서 읽은 내용</h3>
        {isClauseField && originalValue
          ? (
            <ol className="guided-clause-list">
              {originalValue.split("\n").flatMap(splitClauseText).map((line, index) => {
                const hint = clausePlainHint(line);
                return (
                  <li key={index}>
                    <span className="guided-clause-list__text">{line}</span>
                    {hint && (
                      <details className="guided-clause-hint">
                        <summary>💡 쉬운 설명 보기</summary>
                        <div className="guided-clause-hint__body">{hint} <span className="guided-clause-hint__ref">(참고)</span></div>
                      </details>
                    )}
                  </li>
                );
              })}
            </ol>
          )
          : <p>{originalValue || "읽은 내용이 없습니다."}</p>}
      </section>

      {mode === "editing" ? (
        <section aria-label="내용 수정">
          <label htmlFor={correctionId}>{`${item.view.label} 수정 내용`}</label>
          {multiline ? (
            <textarea
              id={correctionId}
              value={editedValue}
              disabled={busy}
              onChange={(event) => {
                setEditedValue(event.target.value);
                setShowEmptyError(false);
              }}
            />
          ) : (
            <input
              id={correctionId}
              type="text"
              value={editedValue}
              disabled={busy}
              onChange={(event) => {
                setEditedValue(event.target.value);
                setShowEmptyError(false);
              }}
            />
          )}
          {showEmptyError && <p role="alert">수정할 내용을 입력해 주세요.</p>}
          <button type="button" disabled={busy} onClick={saveChange}>수정한 내용 사용하기</button>
          <button type="button" disabled={busy} onClick={cancelEditing}>수정 취소</button>
        </section>
      ) : (
        <div>
          <button type="button" disabled={busy} onClick={onConfirm}>네, 맞아요</button>
          <button type="button" className="secondary" disabled={busy} onClick={startEditing}>직접 고칠게요</button>
          <button
            type="button"
            className="ghost-button"
            disabled={busy}
            onClick={() => setMode("cannot-verify")}
          >
            문서에서 확인하기 어려워요
          </button>
        </div>
      )}

      {mode === "cannot-verify" && (
        <fieldset disabled={busy}>
          <legend>확인하기 어려운 이유</legend>
          <label>
            <input
              type="radio"
              name={cannotVerifyName}
              onChange={() => onCannotVerify("not_stated")}
            />
            문서에 적혀 있지 않아요
          </label>
          <label>
            <input
              type="radio"
              name={cannotVerifyName}
              onChange={() => onCannotVerify("unreadable")}
            />
            글자가 흐려서 확인하기 어려워요
          </label>
          <label>
            <input
              type="radio"
              name={cannotVerifyName}
              onChange={() => onCannotVerify("unknown_location")}
            />
            어디를 봐야 할지 모르겠어요
          </label>
        </fieldset>
      )}
    </article>
  );
}
