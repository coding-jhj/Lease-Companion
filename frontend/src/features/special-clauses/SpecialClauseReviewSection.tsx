import type { SpecialClauseGuidanceDto, SpecialClauseReviewDto } from "../../types/api";
import { SpecialClauseCard } from "./SpecialClauseCard";

export function SpecialClauseReviewSection({
  reviews,
  guidance,
  generationFailed,
}: {
  reviews: SpecialClauseReviewDto[];
  guidance: SpecialClauseGuidanceDto[];
  generationFailed: boolean;
}) {
  if (reviews.length === 0) return null;
  const guidanceByClause = new Map(guidance.map((item) => [item.clause_id, item]));

  return <section className="special-clause-review-section" aria-labelledby="special-clause-review-title">
    <div className="section-heading"><p>계약서 원문과 Python 판정·공식 근거를 함께 확인하세요</p><h2 id="special-clause-review-title">확인이 필요한 특약</h2></div>
    {generationFailed && <p className="notice" role="status">안내 생성은 실패했지만 특약 원문과 Python 판정은 그대로 표시합니다.</p>}
    <div className="special-clause-card-list">
      {reviews.map((review, index) => <SpecialClauseCard
        key={review.clause_id}
        review={review}
        guidance={guidanceByClause.get(review.clause_id) ?? null}
        index={index}
        generationFailed={generationFailed}
      />)}
    </div>
  </section>;
}
