import type { DamagePatternComparisonDto, JudgmentGuidanceDto, RuleGuidanceDto } from "../../types/api";

type Guidance = RuleGuidanceDto | JudgmentGuidanceDto;

function idOf(item: Guidance) { return "rule_id" in item ? item.rule_id : item.judgment_id; }

// 카드에는 대표 질문 하나만 두고 나머지는 접는다. 같은 질문이 "물어볼 말" 탭에도 있으므로
// 여기서 목록을 통째로 반복하지 않는다.
export function DetectedSignalSection({ patterns, guidance }: { patterns: DamagePatternComparisonDto[]; guidance: Guidance[] }) {
  const signals = patterns.filter((item) => item.status === "관련 확인 신호 있음");
  if (signals.length === 0) return null;
  const guidanceById = new Map(guidance.map((item) => [idOf(item), item]));
  return <section className="detected-signals" aria-labelledby="detected-signals-title">
    <h3 id="detected-signals-title">입금·서명 전에 먼저 확인할 항목</h3>
    <div className="detected-signals__grid">{signals.map((signal) => {
      const linked = [...signal.related_judgment_ids, ...signal.related_rule_ids].map((id) => guidanceById.get(id)).filter((item): item is Guidance => Boolean(item));
      const questions = [...new Set(linked.flatMap((item) => item.questions ?? []))];
      const requests = [...new Set(linked.flatMap((item) => item.request_templates ?? []))];
      const actions = [...new Set(linked.flatMap((item) => item.signing_checklist_items.map((entry) => entry.text)))];
      const [leadQuestion, ...restQuestions] = questions;
      const foldedCount = restQuestions.length + requests.length + actions.length;
      return <article className="detected-signal-card" key={signal.pattern_id}>
        <span>반드시 확인</span><h4>{signal.pattern_name}</h4><p>{signal.reason}</p>
        {leadQuestion && <div className="detected-signal-card__lead">
          <strong>먼저 물어볼 말</strong>
          <p>{leadQuestion}</p>
        </div>}
        {foldedCount > 0 && <details>
          <summary>질문·행동 {foldedCount}개 더 보기</summary>
          {restQuestions.length > 0 && <div><strong>다른 질문</strong><ul>{restQuestions.map((text) => <li key={text}>{text}</li>)}</ul></div>}
          {requests.length > 0 && <div><strong>수정 요청 문구</strong><ul>{requests.map((text) => <li key={text}>{text}</li>)}</ul></div>}
          {actions.length > 0 && <div><strong>확인 행동</strong><ul>{actions.map((text) => <li key={text}>{text}</li>)}</ul></div>}
        </details>}
      </article>;
    })}</div>
  </section>;
}
