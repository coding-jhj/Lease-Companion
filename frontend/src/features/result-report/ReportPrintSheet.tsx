import type {
  DamagePatternComparisonDto,
  JudgmentGuidanceDto,
  JudgmentResultDto,
  RuleGuidanceDto,
  RuleResultDto,
  SpecialClauseGuidanceDto,
  SpecialClauseReviewDto,
  StageGuidanceDto,
} from "../../types/api";
import { buildQuestionGroups } from "../question-cards/DefenseActionHub";
import { buildActionFirstItems } from "./actionFirstViewModel";

type Guidance = RuleGuidanceDto | JudgmentGuidanceDto;
type Result = RuleResultDto | JudgmentResultDto;

function unique(values: string[]) {
  return [...new Set(values.map((value) => value.trim()).filter(Boolean))];
}

function PrintList({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null;
  return <section><h3>{title}</h3><ul>{items.map((item) => <li key={item}>{item}</li>)}</ul></section>;
}

function resultId(result: Result) {
  return "rule_id" in result ? result.rule_id : result.judgment_id;
}

function resultName(result: Result) {
  return "rule_name" in result ? result.rule_name : result.judgment_name;
}

function officialSources(pattern: DamagePatternComparisonDto) {
  return pattern.official_sources.map((source) => source.article_or_section
    ? `${source.title} ${source.article_or_section}`
    : source.title);
}

export function ReportPrintSheet({
  contractId,
  patterns,
  actionResults,
  results,
  guidance,
  specialClauseReviews,
  specialClauseGuidance,
  stageGuidance,
}: {
  contractId: number;
  patterns: DamagePatternComparisonDto[];
  actionResults: Result[];
  results: Result[];
  guidance: Guidance[];
  specialClauseReviews: SpecialClauseReviewDto[];
  specialClauseGuidance: SpecialClauseGuidanceDto[];
  stageGuidance: StageGuidanceDto | null;
}) {
  const actionItems = buildActionFirstItems(actionResults, guidance, stageGuidance);
  const questionGroups = buildQuestionGroups(results, guidance, stageGuidance);
  const hasQuestions = Object.values(questionGroups).some((items) => items.length > 0);
  const stageGroups = [
    ["계약 전", unique(stageGuidance?.before_contract_actions ?? stageGuidance?.signing_checklist ?? [])],
    ["계약 중", unique(stageGuidance?.during_contract_actions ?? stageGuidance?.signing_checklist ?? [])],
    ["잔금·입주 당일", unique(stageGuidance?.closing_day_actions ?? [])],
    ["계약 후", unique(stageGuidance?.after_contract_actions ?? stageGuidance?.post_contract_actions ?? [])],
    ["보관할 자료", unique(stageGuidance?.record_retention ?? [])],
  ] as const;
  const clauseGuidanceById = new Map(specialClauseGuidance.map((item) => [item.clause_id, item]));
  const hasDetailData = results.length > 0 || specialClauseReviews.length > 0;

  return <article className="report-print-sheet" aria-hidden="true">
    <header><p>슬기로운 계약생활</p><h1>내 계약 확인 결과</h1><span>계약 건 #{contractId} · 출력일 {new Date().toLocaleDateString("ko-KR")}</span></header>
    {actionItems.length > 0 && <section>
      <h2>지금 먼저 확인할 일</h2>
      <ul>{actionItems.map((item) => <li key={item.id}><strong>{item.priority} · {item.timing}</strong><br />{item.title}</li>)}</ul>
    </section>}
    {hasQuestions && <section>
      <h2>물어볼 말</h2>
      <PrintList title="중개사에게 물어볼 말" items={questionGroups["중개사"]} />
      <PrintList title="임대인에게 물어볼 말" items={questionGroups["임대인"]} />
      <PrintList title="내가 문서에서 다시 볼 것" items={questionGroups["내가 다시 확인"]} />
    </section>}
    {stageGroups.some(([, items]) => items.length > 0) && <section>
      <h2>계약 단계별 할 일</h2>
      {stageGroups.map(([title, items]) => <PrintList key={title} title={title} items={items} />)}
    </section>}
    {results.length > 0 && <section>
      <h2>판단 이유</h2>
      <ul>{results.map((result) => <li key={resultId(result)}><strong>{resultName(result)}</strong><br />{result.reason}</li>)}</ul>
    </section>}
    {hasDetailData && <section>
      <h2>문서 근거와 세부 판정 정보</h2>
      {results.map((result) => <article className="report-print-sheet__clause" key={resultId(result)}>
        <h3>{resultName(result)}</h3>
        <p><strong>세부 판정:</strong> {resultId(result)} · 상태: {result.status} · 시급도: {result.urgency}</p>
        <p><strong>공식 근거:</strong> {result.evidence_sources.length > 0
          ? result.evidence_sources.map((source) => source.article_or_section ? `${source.title} ${source.article_or_section}` : source.title).join(", ")
          : "현재 연결된 공식 근거 없음"}</p>
        <small>{result.limitations}</small>
      </article>)}
      {specialClauseReviews.length > 0 && <h3>확인이 필요한 특약</h3>}
      {specialClauseReviews.map((review, index) => {
        const item = clauseGuidanceById.get(review.clause_id);
        return <article className="report-print-sheet__clause" key={review.clause_id}>
          <h3>특약 {index + 1}</h3><blockquote>{review.original_text}</blockquote>
          <p><strong>판정:</strong> {review.status} · {review.urgency}</p>
          <p><strong>쉬운 설명:</strong> {item?.plain_explanation ?? review.reason}</p>
          <p><strong>공식 근거:</strong> {review.evidence_sources.length > 0
            ? review.evidence_sources.map((source) => source.article_or_section ? `${source.title} ${source.article_or_section}` : source.title).join(", ")
            : "현재 연결된 공식 근거 없음"}</p>
          {item && <><PrintList title="확인 질문" items={item.confirmation_questions} /><PrintList title="수정 요청" items={item.revision_requests} /></>}
          <small>{review.limitations}</small>
        </article>;
      })}
    </section>}
    {patterns.length > 0 && <section>
      <h2>비슷한 상황에서 확인할 점</h2>
      {patterns.map((pattern) => <article className="report-print-sheet__clause" key={pattern.pattern_id}>
        <h3>{pattern.pattern_name}</h3>
        <p><strong>제출 자료 기준:</strong> {pattern.status}</p>
        <p>{pattern.reason}</p>
        <PrintList title="공식 근거" items={officialSources(pattern)} />
        <PrintList title="유사 참고 사례" items={pattern.reference_cases.map((item) => item.title)} />
        <small>{pattern.limitations}</small>
      </article>)}
    </section>}
    <footer>이 문서는 계약의 안전·위법 여부를 판정하는 법률 의견서가 아닙니다. 서명·송금 전에 확인할 질문과 행동을 정리한 자료입니다.</footer>
  </article>;
}
