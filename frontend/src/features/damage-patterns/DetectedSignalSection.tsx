import type { DamagePatternComparisonDto, JudgmentGuidanceDto, RuleGuidanceDto } from "../../types/api";

type Guidance = RuleGuidanceDto | JudgmentGuidanceDto;

function idOf(item: Guidance) { return "rule_id" in item ? item.rule_id : item.judgment_id; }

export function DetectedSignalSection({ patterns, guidance }: { patterns: DamagePatternComparisonDto[]; guidance: Guidance[] }) {
  const signals = patterns.filter((item) => item.status === "관련 확인 신호 있음");
  if (signals.length === 0) return null;
  const guidanceById = new Map(guidance.map((item) => [idOf(item), item]));
  return <section className="detected-signals" aria-labelledby="detected-signals-title">
    <div className="section-heading"><p>입금이나 서명 전에 먼저 확인하세요</p><h2 id="detected-signals-title">지금 반드시 확인할 항목</h2></div>
    <div className="detected-signals__grid">{signals.map((signal) => {
      const linked = [...signal.related_judgment_ids, ...signal.related_rule_ids].map((id) => guidanceById.get(id)).filter((item): item is Guidance => Boolean(item));
      const questions = [...new Set(linked.flatMap((item) => item.questions ?? []))];
      const requests = [...new Set(linked.flatMap((item) => item.request_templates ?? []))];
      const actions = [...new Set(linked.flatMap((item) => item.signing_checklist_items.map((entry) => entry.text)))];
      return <article className="detected-signal-card" key={signal.pattern_id}>
        <span>반드시 확인</span><h3>{signal.pattern_name}</h3><p>{signal.reason}</p>
        {questions.length > 0 && <div><strong>먼저 물어볼 질문</strong><ul>{questions.map((text) => <li key={text}>{text}</li>)}</ul></div>}
        {requests.length > 0 && <div><strong>수정 요청 문구</strong><ul>{requests.map((text) => <li key={text}>{text}</li>)}</ul></div>}
        {actions.length > 0 && <div><strong>확인 행동</strong><ul>{actions.map((text) => <li key={text}>{text}</li>)}</ul></div>}
      </article>;
    })}</div>
  </section>;
}
