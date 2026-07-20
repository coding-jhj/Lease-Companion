import { useState } from "react";
import type { JudgmentResultDto, RuleResultDto, Urgency } from "../../types/api";
import { EvidenceDisclosure } from "../evidence-sources/EvidenceDisclosure";

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

function resultScope(item: ReportResultDto) {
  if ("rule_id" in item) return item.judgment_id ?? "사실 플래그";
  return "조항 분류 판정";
}

function cannotJudgeNow(item: ReportResultDto) {
  return item.status === "확인 불가"
    || item.status === "적용 제외"
    || ("rule_id" in item && externalDataRuleIds.has(item.rule_id));
}

function ResultCard({ item, idPrefix }: { item: ReportResultDto; idPrefix: string }) {
  return (
    <article className="result-card">
      <p className="result-meta">
        <strong>{resultId(item)}</strong>
        {" · "}
        {resultScope(item)}
        {" · 상태: "}{item.status}
        {" · 시급도: "}{item.urgency}
      </p>
      <h3>{resultName(item)}</h3>
      <p>{item.reason}</p>
      <details className="result-support">
        <summary>근거와 판정 한계 확인</summary>
        <EvidenceDisclosure
          idPrefix={idPrefix}
          sources={item.evidence_sources}
          limitations={item.limitations}
        />
      </details>
    </article>
  );
}

export function PriorityGroups({
  items,
  idPrefix = "priority",
  focusPriority,
}: {
  items: ReportResultDto[];
  idPrefix?: string;
  focusPriority?: DisplayPriority;
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
            {expanded && <div className="priority-group__items" id={`${headingId}-items`}>
              {groupItems.length === 0 ? (
                <p className="group-empty">해당하는 확인 항목이 없습니다.</p>
              ) : groupItems.map((item) => (
                <ResultCard
                  item={item}
                  idPrefix={`${idPrefix}-${resultId(item)}`}
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
            <div className="priority-group__items" id={`${idPrefix}-unavailable-items`}>
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
