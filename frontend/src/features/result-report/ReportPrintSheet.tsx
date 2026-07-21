import type {
  DamagePatternComparisonDto,
  JudgmentGuidanceDto,
  RuleGuidanceDto,
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
  stageGuidance,
}: {
  contractId: number;
  patterns: DamagePatternComparisonDto[];
  guidance: Guidance[];
  stageGuidance: StageGuidanceDto | null;
}) {
  const questions = unique(guidance.flatMap((item) => item.questions));
  const requests = unique(guidance.flatMap((item) => item.request_templates ?? []));
  return <article className="report-print-sheet" aria-hidden="true">
    <header><p>슬기로운 계약생활</p><h1>임차인 방어 리포트</h1><span>계약 건 #{contractId} · 출력일 {new Date().toLocaleDateString("ko-KR")}</span></header>
    <section><h2>주요 금전피해 유형 비교</h2>
      <table><thead><tr><th>피해 유형</th><th>분석 결과</th><th>판단 근거</th></tr></thead>
        <tbody>{patterns.map((item) => <tr key={item.pattern_id}><td>{item.pattern_name}</td><td>{item.status}</td><td>{item.reason}<small>{item.limitations}</small></td></tr>)}</tbody>
      </table>
    </section>
    <PrintList title="임대인·중개사에게 물어볼 질문" items={questions} />
    <PrintList title="수정·추가 요청 문구" items={requests} />
    <PrintList title="계약 전" items={stageGuidance?.before_contract_actions ?? []} />
    <PrintList title="계약 중" items={stageGuidance?.during_contract_actions ?? []} />
    <PrintList title="잔금·입주 당일" items={stageGuidance?.closing_day_actions ?? []} />
    <PrintList title="계약 후" items={stageGuidance?.after_contract_actions ?? []} />
    <PrintList title="보관할 자료" items={stageGuidance?.record_retention ?? []} />
    <footer>이 리포트는 제출 자료에서 확인할 항목을 정리한 자료이며 계약의 안전성·적법성 또는 피해 발생 여부를 확정하지 않습니다.</footer>
  </article>;
}
