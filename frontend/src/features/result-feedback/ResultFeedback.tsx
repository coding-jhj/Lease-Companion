import { useEffect, useState, type FormEvent } from "react";
import { mvpService } from "../../services/mvpService";
import type { FeedbackDto } from "../../types/api";

export function ResultFeedback({ contractId }: { contractId: number }) {
  const [items, setItems] = useState<FeedbackDto[]>([]);
  const [content, setContent] = useState("");
  const [rating, setRating] = useState<number | null>(null);
  const [loadingError, setLoadingError] = useState("");
  const [submitError, setSubmitError] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    let active = true;
    void mvpService.getFeedback(contractId)
      .then((response) => { if (active) setItems(response); })
      .catch((error) => {
        if (active) setLoadingError(error instanceof Error ? error.message : "피드백 이력을 불러오지 못했습니다.");
      });
    return () => { active = false; };
  }, [contractId]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const trimmed = content.trim();
    if (!trimmed) return;
    setSubmitting(true);
    setSubmitError("");
    setSubmitted(false);
    try {
      const created = await mvpService.createFeedback(contractId, { content: trimmed, rating });
      setItems((current) => [created, ...current]);
      setContent("");
      setRating(null);
      setSubmitted(true);
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : "피드백을 저장하지 못했습니다.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="feedback-card" aria-labelledby="feedback-title">
      <h2 id="feedback-title">리포트 의견 보내기</h2>
      <form className="stack" onSubmit={submit}>
        <label>평점
          <select value={rating ?? ""} onChange={(event) => setRating(event.target.value ? Number(event.target.value) : null)}>
            <option value="">선택 안 함</option>
            {[1, 2, 3, 4, 5].map((value) => <option key={value} value={value}>{value}점</option>)}
          </select>
        </label>
        <label>의견
          <textarea maxLength={2000} required value={content} onChange={(event) => setContent(event.target.value)} />
        </label>
        {submitError && <p className="error" role="alert">{submitError}</p>}
        {submitted && <p className="notice" role="status">의견이 저장되었습니다.</p>}
        <button type="submit" disabled={submitting || !content.trim()}>{submitting ? "저장 중…" : "의견 저장"}</button>
      </form>
      {loadingError && <p className="error" role="alert">{loadingError}</p>}
      {items.length > 0 && (
        <details>
          <summary>이전 의견 {items.length}건</summary>
          <ul className="feedback-history">
            {items.map((item) => <li key={item.id}>{item.rating ? `${item.rating}점 · ` : ""}{item.content}</li>)}
          </ul>
        </details>
      )}
    </section>
  );
}
