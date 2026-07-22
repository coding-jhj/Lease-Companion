import { EvidenceDisclosure } from "../evidence-sources/EvidenceDisclosure";
import { displayPriorityForUrgency } from "../judgment-results/PriorityGroups";
import type { SpecialClauseGuidanceDto, SpecialClauseReviewDto } from "../../types/api";

function GuidanceList({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null;
  return <section className="special-clause-card__guidance"><h4>{title}</h4><ul>{items.map((item) => <li key={item}>{item}</li>)}</ul></section>;
}

export function SpecialClauseCard({
  review,
  guidance,
  index,
  generationFailed,
}: {
  review: SpecialClauseReviewDto;
  guidance: SpecialClauseGuidanceDto | null;
  index: number;
  generationFailed: boolean;
}) {
  const priority = displayPriorityForUrgency(review.urgency);
  const explanation = guidance?.plain_explanation
    ?? (generationFailed
      ? "안내 생성에 실패했습니다. Python 판정 이유와 공식 근거를 먼저 확인하세요."
      : "생성된 쉬운 설명이 없습니다. Python 판정 이유와 공식 근거를 확인하세요.");

  return <article className="special-clause-card" data-priority={priority}>
    <header className="special-clause-card__header">
      <div><span className="special-clause-card__index">특약 {index + 1}</span><h3>직접 확인할 특약</h3></div>
      <span className="special-clause-card__priority">{priority}</span>
    </header>
    <blockquote><strong>계약서 원문</strong><p>{review.original_text}</p></blockquote>
    <p className="special-clause-card__meta">상태: {review.status} · 시급도: {review.urgency}</p>
    <EvidenceDisclosure
      sources={review.evidence_sources}
      limitations={review.limitations}
      explanation={explanation}
      financialImpact={review.reason}
      financialImpactLabel="확인이 필요한 이유"
      idPrefix={`special-clause-${review.clause_id}`}
      order="explanation-first"
    />
    <GuidanceList title="계약 상대방에게 확인할 질문" items={guidance?.confirmation_questions ?? []} />
    <GuidanceList title="수정 요청 문구" items={guidance?.revision_requests ?? []} />
  </article>;
}
