import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import type { JudgmentResultDto, RuleResultDto, Urgency } from "../../types/api";
import { EvidenceDisclosure } from "../evidence-sources/EvidenceDisclosure";
import { plainGuideById } from "./plainGuides";
// 타입만 가져온다. actionFirstViewModel이 이 파일의 함수를 쓰므로 값 import는 순환이 된다.
import type { ActionFirstItem } from "../result-report/actionFirstViewModel";

export type DisplayPriority = "반드시 확인" | "확인 권장" | "일반 확인";

const priorityMeta: Record<DisplayPriority, { icon: string; description: string }> = {
  "반드시 확인": { icon: "!", description: "계약 진행 전에 우선 확인이 필요한 항목" },
  "확인 권장": { icon: "?", description: "계약 전후에 추가 확인을 권장하는 항목" },
  "일반 확인": { icon: "i", description: "알아두고 확인할 일반 정보" },
};

const priorityOrder: DisplayPriority[] = ["반드시 확인", "확인 권장", "일반 확인"];

export function displayPriorityForUrgency(urgency: Urgency): DisplayPriority {
  if (urgency === "즉시 확인" || urgency === "분석 불가") return "반드시 확인";
  if (urgency === "계약 전 확인" || urgency === "계약 직후 조치") return "확인 권장";
  return "일반 확인";
}

type ReportResultDto = RuleResultDto | JudgmentResultDto;

const externalDataRuleIds = new Set(["R20", "R21", "R22"]);

function resultId(item: ReportResultDto) {
  return "rule_id" in item ? item.rule_id : item.judgment_id;
}

function resultName(item: ReportResultDto) {
  return "rule_name" in item ? item.rule_name : item.judgment_name;
}

// 상태 칩 색. 결과 상태 9개를 화면 톤 3개로만 나눈다(판정 자체는 바꾸지 않는다).
const WARN_STATUSES = new Set(["불일치", "불명확", "미기재", "상충 가능"]);
const OK_STATUSES = new Set(["일치", "명확"]);

function statusTone(status: string): "warn" | "ok" | "neutral" {
  if (WARN_STATUSES.has(status)) return "warn";
  if (OK_STATUSES.has(status)) return "ok";
  return "neutral";
}

export function cannotJudgeNow(item: ReportResultDto) {
  return item.status === "확인 불가"
    || item.status === "적용 제외"
    || ("rule_id" in item && externalDataRuleIds.has(item.rule_id));
}

function ResultCard({ item, idPrefix, action, anchorId }: {
  item: ReportResultDto;
  idPrefix: string;
  action?: ActionFirstItem;
  anchorId?: string;
}) {
  // 판정(J) 가이드 우선, 없으면 규칙 id(R) 가이드로 폴백 — J 미매핑 규칙도 개별 안내를 보이게.
  const guide = plainGuideById(item.judgment_id ?? ("rule_id" in item ? item.rule_id : null));
  const [isModalOpen, setIsModalOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const titleId = `${idPrefix}-detail-title`;
  const question = action?.question ?? item.question;
  const questionTarget = action?.questionTarget ?? "내가 다시 확인";

  useEffect(() => {
    if (!isModalOpen) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeRef.current?.focus();
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setIsModalOpen(false);
    };
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", closeOnEscape);
      triggerRef.current?.focus();
    };
  }, [isModalOpen]);

  return (
    <article className="result-card" id={anchorId}>
      <div className="result-card__meta">
        {action && <span>{action.timing}</span>}
        <span className="result-card__status" data-tone={statusTone(item.status)}>{item.status}</span>
      </div>
      <h3>{resultName(item)}</h3>
      <p className="result-card__summary">{action?.reason ?? item.reason}</p>
      <button
        ref={triggerRef}
        type="button"
        className="result-card__detail-button"
        aria-haspopup="dialog"
        onClick={() => setIsModalOpen(true)}
      >
        자세히 보기
      </button>
      {isModalOpen && createPortal(
        <div
          className="damage-pattern-modal__backdrop"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) setIsModalOpen(false);
          }}
        >
          <section
            className="damage-pattern-modal result-detail-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby={titleId}
          >
            <header className="damage-pattern-modal__header">
              <div>
                <span className="damage-pattern-modal__eyebrow">계약 확인 항목</span>
                <h2 id={titleId}>{resultName(item)}</h2>
              </div>
              <button
                ref={closeRef}
                type="button"
                className="damage-pattern-modal__close"
                aria-label="창 닫기"
                onClick={() => setIsModalOpen(false)}
              >
                <span className="damage-pattern-modal__close-icon" aria-hidden="true" />
              </button>
            </header>
            <div className="damage-pattern-modal__body">
              <p className="result-detail-modal__reason">{action?.reason ?? item.reason}</p>
              {question && (
                <div className="result-card__question">
                  <strong>{questionTarget}</strong>
                  <span>{question}</span>
                </div>
              )}
              <EvidenceDisclosure
                idPrefix={idPrefix}
                sources={item.evidence_sources}
                limitations={item.limitations}
                explanation={guide.explanation}
                financialImpact={guide.financialImpact}
                hideLimitations
                damagePatternGuide={{ checkText: guide.explanation }}
              />
            </div>
          </section>
        </div>,
        document.body,
      )}
    </article>
  );
}

export function PriorityGroups({
  items,
  idPrefix = "priority",
  focusPriority,
  actionById,
}: {
  items: ReportResultDto[];
  idPrefix?: string;
  focusPriority?: DisplayPriority;
  /** 시점·질문·정리된 설명. 있으면 카드가 "먼저 할 일" 정보를 함께 보여준다. */
  actionById?: Map<string, ActionFirstItem>;
}) {
  const [expandedPriorities, setExpandedPriorities] = useState<DisplayPriority[]>(["반드시 확인"]);
  const [showUnavailable, setShowUnavailable] = useState(false);
  const actionableItems = items.filter((item) => !cannotJudgeNow(item));
  const unavailableItems = items.filter(cannotJudgeNow);

  function togglePriority(priority: DisplayPriority) {
    setExpandedPriorities((current) => current.includes(priority)
      ? current.filter((item) => item !== priority)
      : [...current, priority]);
  }

  return (
    <div className="priority-groups">
      {priorityOrder.map((priority) => {
        const groupItems = actionableItems.filter((item) => displayPriorityForUrgency(item.urgency) === priority);
        const meta = priorityMeta[priority];
        const headingId = `${idPrefix}-${priority.replaceAll(" ", "-")}`;
        const expanded = expandedPriorities.includes(priority);

        return (
          <section
            id={priority === focusPriority ? "first-priority-group" : undefined}
            className="priority-group"
            data-priority={priority}
            aria-labelledby={headingId}
            key={priority}
          >
            <button
              className="priority-group__header priority-group__toggle"
              type="button"
              aria-expanded={expanded}
              aria-controls={`${headingId}-items`}
              onClick={() => togglePriority(priority)}
            >
              <span className="signal-icon" aria-hidden="true">{meta.icon}</span>
              <div>
                <h2 id={headingId}>{priority}</h2>
                <p>{meta.description}</p>
              </div>
              <span className="priority-count" aria-label={`${priority} ${groupItems.length}개`}>{groupItems.length}</span>
              <span className="collapse-arrow" aria-hidden="true">{expanded ? "▾" : "▸"}</span>
            </button>
            {expanded && <div
              className="priority-group__items priority-group__items--three-column"
              id={`${headingId}-items`}
            >
              {groupItems.length === 0 ? (
                <p className="group-empty">해당하는 확인 항목이 없습니다.</p>
              ) : groupItems.map((item, index) => (
                <ResultCard
                  item={item}
                  idPrefix={`${idPrefix}-${resultId(item)}`}
                  action={actionById?.get(resultId(item))}
                  anchorId={priority === focusPriority && index === 0 ? "first-action-item" : undefined}
                  key={resultId(item)}
                />
              ))}
            </div>}
          </section>
        );
      })}
      {unavailableItems.length > 0 && (
        <section className="unavailable-results" aria-labelledby={`${idPrefix}-unavailable-title`}>
          <button
            className="unavailable-results__toggle"
            type="button"
            aria-expanded={showUnavailable}
            aria-controls={`${idPrefix}-unavailable-items`}
            onClick={() => setShowUnavailable((current) => !current)}
          >
            <span id={`${idPrefix}-unavailable-title`}>지금 판단할 수 없는 항목 {unavailableItems.length}개</span>
            <span className="collapse-arrow" aria-hidden="true">{showUnavailable ? "▾" : "▸"}</span>
          </button>
          {showUnavailable && (
            <div className="priority-group__items priority-group__items--three-column" id={`${idPrefix}-unavailable-items`}>
              {unavailableItems.map((item) => (
                <ResultCard
                  item={item}
                  idPrefix={`${idPrefix}-${resultId(item)}`}
                  key={resultId(item)}
                />
              ))}
            </div>
          )}
        </section>
      )}
    </div>
  );
}
