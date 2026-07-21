import type { StageGuidanceDto } from "../../types/api";

function StageList({ title, items }: { title: string; items: string[] }) {
  return (
    <section className="stage-guidance__group">
      <h3>{title}</h3>
      {items.length > 0
        ? <ul>{items.map((item) => <li key={item}>{item}</li>)}</ul>
        : <p className="group-empty">현재 단계에 추가로 안내할 항목이 없습니다.</p>}
    </section>
  );
}

export function StageGuidance({ guidance }: { guidance: StageGuidanceDto }) {
  return (
    <section className="stage-guidance" aria-labelledby="stage-guidance-title">
      <h2 id="stage-guidance-title">계약 단계별 안내</h2>
      <div className="stage-guidance__grid">
        <StageList title="계약 전" items={guidance.before_contract_actions ?? guidance.signing_checklist} />
        <StageList title="계약 중" items={guidance.during_contract_actions ?? guidance.signing_checklist} />
        <StageList title="잔금·입주 당일" items={guidance.closing_day_actions ?? []} />
        <StageList title="계약 후" items={guidance.after_contract_actions ?? guidance.post_contract_actions} />
        <StageList title="보관해야 할 자료" items={guidance.record_retention} />
      </div>
    </section>
  );
}
