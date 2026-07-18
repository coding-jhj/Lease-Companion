import type { JudgmentGuidanceDto, RuleGuidanceDto } from "../../types/api";

function TextList({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null;
  return (
    <section className="guidance-section">
      <h4>{title}</h4>
      <ul>{items.map((item) => <li key={item}>{item}</li>)}</ul>
    </section>
  );
}

type GuidanceDto = RuleGuidanceDto | JudgmentGuidanceDto;

function guidanceId(item: GuidanceDto) {
  return "rule_id" in item ? item.rule_id : item.judgment_id;
}

export function GenerationGuidance({ items }: { items: GuidanceDto[] }) {
  if (items.length === 0) return null;
  return (
    <section className="guidance-list" aria-labelledby="guidance-title">
      <h2 id="guidance-title">확인 질문과 다음 행동</h2>
      {items.map((item) => (
        <article className="guidance-card" key={guidanceId(item)}>
          <div className="guidance-card__header">
            <strong>{guidanceId(item)}</strong>
            {item.generation_method === "template_fallback" && (
              <span className="fallback-badge">안전한 기본 안내</span>
            )}
          </div>
          <p>{item.explanation}</p>
          <TextList title="물어볼 질문" items={item.questions} />
          <TextList title="서명 전 체크리스트" items={item.signing_checklist_items.map((entry) => entry.text)} />
          <TextList title="계약 직후 행동" items={item.post_contract_action_items.map((entry) => entry.text)} />
        </article>
      ))}
    </section>
  );
}
