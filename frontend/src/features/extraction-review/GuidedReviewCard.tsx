import { useEffect, useId, useState } from "react";

import type { ReviewQueueItem } from "./reviewQueue";
import { formatClauseText, splitClausesForDisplay } from "./viewModel";

type CannotVerifyReason = "not_stated" | "unreadable" | "unknown_location";

// 조항 쉬운 뜻(참고용). 표준임대차계약서 본문 조와 자주 나오는 특약을 다룬다.
// 사실 기반 요약이며, 매칭 안 되면 표시하지 않는다(임의 생성 금지). 구체 패턴을 먼저 둔다.
const CLAUSE_PLAIN_HINTS: Array<{ match: RegExp; text: string }> = [
  // 표준계약서 본문 조 (구체 → 일반 순서)
  { match: /비용의 정산|장기수선충당금|공과금과 관리비를 정산/, text: "계약이 끝날 때 공과금·관리비를 정산하고, 임차인이 미리 낸 장기수선충당금을 임대인에게 돌려받는 것에 대한 조항입니다." },
  { match: /갱신요구와 거절|계약갱신을 요구|갱신을 요구할 수 있다|계약갱신.{0,6}거절|갱신의 요구를 거절|실거주 등.*사유/, text: "계약이 끝나기 6개월~2개월 전에 임차인이 계약 연장을 요구할 수 있고, 임대인은 실거주 등 정해진 사유가 있을 때만 거절할 수 있다는 조항입니다." },
  { match: /2기의 차임액|차임액에 달하도록|계약의 해지/, text: "집이 크게 망가져 살 수 없거나 월세를 2번분 밀리는 등의 경우, 계약을 중간에 끝낼 수 있다는 조항입니다." },
  { match: /채무불이행|손해배상/, text: "한쪽이 약속을 지키지 않으면 상대가 기간을 정해 이행을 요구하고, 그래도 안 되면 계약을 해제하고 손해배상을 청구할 수 있다는 조항입니다." },
  { match: /계약의 해제|중도금.{0,6}지급하기 전|계약금의 배액/, text: "잔금(또는 중도금)을 내기 전에 계약을 무를 때 계약금을 어떻게 처리하는지 정한 조항입니다. 보통 받은 쪽은 배액 반환, 낸 쪽은 포기합니다." },
  { match: /입주 전 수리|수리가 필요한 시설물|비용부담에 관하여/, text: "입주 전에 고쳐야 할 곳과 그 비용을 누가 낼지 미리 정하는 조항입니다." },
  { match: /임대차기간|사용·수익할 수 있는 상태|목적대로 사용/, text: "집을 언제부터 쓸 수 있는지(인도일)와 계약이 얼마 동안 유지되는지를 정하는 조항입니다." },
  { match: /보증금과 차임|차임 및 관리비|보증금.{0,4}차임.{0,4}관리비/, text: "보증금·월세·관리비를 각각 얼마씩, 언제 낼지 정하는 기본 조항입니다." },
  { match: /중개보수/, text: "중개사에게 낼 수수료(중개보수)의 금액과 부담 방법을 정한 조항입니다." },
  { match: /중개대상물.{0,6}확인|중개대상물 확인·설명서|업무보증관계증서/, text: "중개사가 집 상태와 권리관계를 확인해 확인·설명서로 교부해야 한다는 조항입니다." },
  // 자주 나오는 특약
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
  compactUnread?: boolean;
  inlineCompact?: boolean;
  completionLabel?: string;
  onChange: (value: string | string[]) => void;
  onConfirm?: () => void;
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
  compactUnread = false,
  inlineCompact = false,
  completionLabel,
  onChange,
  onConfirm,
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
  const [mode, setMode] = useState<"view" | "editing" | "cannot-verify">(inlineCompact ? "editing" : "view");
  const [editedValue, setEditedValue] = useState(originalValue);
  const [showEmptyError, setShowEmptyError] = useState(false);

  useEffect(() => {
    setMode(inlineCompact ? "editing" : "view");
    setEditedValue(originalValue);
    setShowEmptyError(false);
  }, [inlineCompact, item.key, originalValue]);

  const numericInput = [
    "balance_payment",
    "balance_payment_korean_amount",
    "contract_payment",
    "contract_payment_korean_amount",
    "deposit",
    "deposit_korean_amount",
    "estimated_housing_value",
    "management_fee",
    "monthly_rent",
    "monthly_rent_korean_amount",
    "senior_claim_amount",
  ].includes(item.fieldName);
  const compactPrompt = item.fieldName === "monthly_rent"
    ? "계약서에 적힌 월세를 입력해 주세요."
    : `${item.view.label} 내용을 확인해 입력해 주세요.`;

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

  const confirmDirectly = () => {
    if (editedValue.trim()) {
      saveChange();
      return;
    }
    setShowEmptyError(false);
    onConfirm?.();
  };

  return (
    <article className="guided-review-card">
      {!inlineCompact && !compactUnread && <h2>{item.title}</h2>}
      {!inlineCompact && <p>{item.prompt}</p>}
      {!inlineCompact && <section aria-label="문서에서 읽은 내용">
        <h3>문서에서 읽은 내용</h3>
        {isClauseField && originalValue
          ? (
            <ol className="guided-clause-list">
              {splitClausesForDisplay(originalValue).map((line, index) => {
                const hint = clausePlainHint(line);
                return (
                  <li key={index}>
                    <span className="guided-clause-list__text">{formatClauseText(line)}</span>
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
      </section>}

      {mode === "editing" ? (
        <section aria-label="내용 수정">
          <label htmlFor={correctionId}>{inlineCompact ? compactPrompt : `${item.view.label} 수정 내용`}</label>
          {inlineCompact && item.view.guidance && <p className="guided-review-card__inline-guidance">{item.view.guidance}</p>}
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
              inputMode={numericInput ? "numeric" : "text"}
              placeholder={numericInput ? "금액 입력" : "내용 입력"}
              value={editedValue}
              disabled={busy}
              onChange={(event) => {
                setEditedValue(event.target.value);
                setShowEmptyError(false);
              }}
            />
          )}
          {showEmptyError && <p role="alert">수정할 내용을 입력해 주세요.</p>}
          {inlineCompact ? (
            <div className="guided-review-card__inline-actions">
              <button type="button" disabled={busy} onClick={saveChange}>저장</button>
              <button type="button" className="secondary" disabled={busy} onClick={confirmDirectly}>
                직접 확인했습니다
              </button>
            </div>
          ) : (
            <button type="button" disabled={busy} onClick={saveChange}>수정한 내용 사용하기</button>
          )}
          {!inlineCompact && <button type="button" disabled={busy} onClick={cancelEditing}>수정 취소</button>}
        </section>
      ) : (
        // 확인은 구역 단위 묶음 버튼이 담당한다. 카드에는 손봐야 할 때 쓰는 두 가지만 남긴다.
        <div className="guided-review-card__actions">
          {completionLabel && <p className="guided-review-card__state" role="status">{completionLabel}</p>}
          <div className="guided-review-card__buttons">
            <button type="button" className="secondary" disabled={busy} onClick={startEditing}>직접 고칠게요</button>
            {!compactUnread && (
              <button
                type="button"
                className="ghost-button"
                disabled={busy}
                onClick={() => setMode("cannot-verify")}
              >
                문서에서 확인하기 어려워요
              </button>
            )}
          </div>
        </div>
      )}

      {!compactUnread && mode === "cannot-verify" && (
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
