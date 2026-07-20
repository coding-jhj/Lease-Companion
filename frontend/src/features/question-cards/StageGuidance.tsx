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
        <StageList title="계약금 입금 전 질문" items={guidance.before_deposit_questions} />
        <StageList title="서명 전 체크리스트" items={guidance.signing_checklist} />
        <StageList title="계약 직후 행동" items={guidance.post_contract_actions} />
        <StageList title="보관해야 할 자료" items={guidance.record_retention} />
      </div>
    </section>
  );
}
