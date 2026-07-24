import { useEffect, useId, useState } from "react";

import type { ReviewQueueItem } from "./reviewQueue";

type CannotVerifyReason = "not_stated" | "unreadable" | "unknown_location";

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
        <p>{originalValue || "읽은 내용이 없습니다."}</p>
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
          <button type="button" disabled={busy} onClick={startEditing}>직접 고칠게요</button>
          <button
            type="button"
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
