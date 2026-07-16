import type { RuleResultDto, Urgency } from "../../types/api";

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

export function PriorityGroups({ items }: { items: RuleResultDto[] }) {
  return (
    <div className="priority-groups">
      {priorityOrder.map((priority) => {
        const groupItems = items.filter((item) => displayPriorityForUrgency(item.urgency) === priority);
        const meta = priorityMeta[priority];
        const headingId = `priority-${priority.replaceAll(" ", "-")}`;

        return (
          <section className="priority-group" data-priority={priority} aria-labelledby={headingId} key={priority}>
            <header className="priority-group__header">
              <span className="signal-icon" aria-hidden="true">{meta.icon}</span>
              <div>
                <h2 id={headingId}>{priority}</h2>
                <p>{meta.description}</p>
              </div>
              <span className="priority-count" aria-label={`${priority} ${groupItems.length}개`}>{groupItems.length}</span>
            </header>
            <div className="priority-group__items">
              {groupItems.length === 0 ? (
                <p className="group-empty">해당하는 확인 항목이 없습니다.</p>
              ) : groupItems.map((item) => (
                <article className="result-card" key={item.rule_id}>
                  <p className="result-meta">
                    <strong>{item.rule_id}</strong>
                    {" · "}
                    {item.judgment_id ?? "사실 플래그"}
                    {" · 상태: "}{item.status}
                    {" · 시급도: "}{item.urgency}
                  </p>
                  <h3>{item.rule_name}</h3>
                  <p>{item.reason}</p>
                  <dl className="result-details">
                    <div>
                      <dt>확인 질문</dt>
                      <dd>{item.question ?? "추가 질문 없음"}</dd>
                    </div>
                    <div>
                      <dt>권장 행동</dt>
                      <dd>{item.recommended_actions.length > 0 ? item.recommended_actions.join(" · ") : "추가 행동 없음"}</dd>
                    </div>
                    <div>
                      <dt>한계</dt>
                      <dd>{item.limitations}</dd>
                    </div>
                  </dl>
                  <div className="evidence-list">
                    <strong>근거 자료</strong>
                    {item.evidence_sources.map((source) => (
                      <p key={source.source_id}>
                        {source.source_url ? <a href={source.source_url}>{source.title}</a> : source.title}
                        {" · "}{source.institution}{source.summary ? " · " + source.summary : ""}
                      </p>
                    ))}
                  </div>
                </article>
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}
