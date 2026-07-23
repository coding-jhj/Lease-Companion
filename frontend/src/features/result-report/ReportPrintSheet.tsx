import type {
  DamagePatternComparisonDto,
  JudgmentGuidanceDto,
  RuleGuidanceDto,
  SpecialClauseGuidanceDto,
  SpecialClauseReviewDto,
  StageGuidanceDto,
} from "../../types/api";

type Guidance = RuleGuidanceDto | JudgmentGuidanceDto;

function unique(values: string[]) { return [...new Set(values.filter((value) => value.trim()))]; }

function PrintList({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null;
  return <section><h2>{title}</h2><ul>{items.map((item) => <li key={item}>{item}</li>)}</ul></section>;
}

export function ReportPrintSheet({
  contractId,
  patterns,
  guidance,
  specialClauseReviews,
  specialClauseGuidance,
  stageGuidance,
}: {
  contractId: number;
  patterns: DamagePatternComparisonDto[];
  guidance: Guidance[];
  specialClauseReviews: SpecialClauseReviewDto[];
  specialClauseGuidance: SpecialClauseGuidanceDto[];
  stageGuidance: StageGuidanceDto | null;
}) {
  const questions = unique(guidance.flatMap((item) => item.questions));
  const requests = unique(guidance.flatMap((item) => item.request_templates ?? []));
  const clauseGuidanceById = new Map(specialClauseGuidance.map((item) => [item.clause_id, item]));
  return <article className="report-print-sheet" aria-hidden="true">
    <header><p>슬기로운 계약생활</p><h1>내 계약 확인 결과</h1><span>계약 건 #{contractId} · 출력일 {new Date().toLocaleDateString("ko-KR")}</span></header>
    <section><h2>주요 금전피해 유형 비교</h2>
      <table><thead><tr><th>피해 유형</th><th>확인 결과</th><th>판단 근거</th></tr></thead>
        <tbody>{patterns.map((item) => <tr key={item.pattern_id}><td>{item.pattern_name}</td><td>{item.status}</td><td>{item.reason}<small>{item.limitations}</small></td></tr>)}</tbody>
      </table>
    </section>
    {specialClauseReviews.length > 0 && <section><h2>확인이 필요한 특약</h2>
      <div className="report-print-sheet__clauses">{specialClauseReviews.map((review, index) => {
        const item = clauseGuidanceById.get(review.clause_id);
        return <article className="report-print-sheet__clause" key={review.clause_id}>
          <h3>특약 {index + 1}</h3><blockquote>{review.original_text}</blockquote>
          <p><strong>판정:</strong> {review.status} · {review.urgency}</p>
          <p><strong>쉬운 설명:</strong> {item?.plain_explanation ?? review.reason}</p>
          <p><strong>공식 근거:</strong> {review.evidence_sources.length > 0
            ? review.evidence_sources.map((source) => `${source.title}${source.article_or_section ? ` ${source.article_or_section}` : ""}`).join(", ")
            : "현재 연결된 공식 근거 없음"}</p>
          {item && <><PrintList title="확인 질문" items={item.confirmation_questions} /><PrintList title="수정 요청" items={item.revision_requests} /></>}
          <small>{review.limitations}</small>
        </article>;
      })}</div>
    </section>}
    <PrintList title="임대인·중개사에게 물어볼 질문" items={questions} />
    <PrintList title="수정·추가 요청 문구" items={requests} />
    <PrintList title="계약 전" items={stageGuidance?.before_contract_actions ?? []} />
    <PrintList title="계약 중" items={stageGuidance?.during_contract_actions ?? []} />
    <PrintList title="잔금·입주 당일" items={stageGuidance?.closing_day_actions ?? []} />
    <PrintList title="계약 후" items={stageGuidance?.after_contract_actions ?? []} />
    <PrintList title="보관할 자료" items={stageGuidance?.record_retention ?? []} />
    <footer>이 확인 결과는 제출 자료에서 확인할 항목을 정리한 자료이며 계약의 안전성·적법성 또는 피해 발생 여부를 확정하지 않습니다.</footer>
  </article>;
}
