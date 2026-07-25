import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ErrorState, LoadingState } from "../../components/feedback/AsyncState";
import { PageShell } from "../../components/layout/PageShell";
import { practiceService } from "../../services/practiceService";
import type { PracticeResultDto } from "../../types/api";
import { getOfficialSourceDisplayNames } from "../../utils/officialSourceNames";

function ResultList({ title, items, emptyText }: { title: string; items: string[]; emptyText: string }) {
  return (
    <section className="practice-result-card">
      <h2>{title}</h2>
      {items.length > 0 ? <ul>{items.map((item) => <li key={item}>{item}</li>)}</ul> : <p>{emptyText}</p>}
    </section>
  );
}

export function PracticeResultPage() {
  const { sessionId = "" } = useParams();
  const [result, setResult] = useState<PracticeResultDto | null>(null);
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [errorMessage, setErrorMessage] = useState("");
  const officialSourceNames = result
    ? getOfficialSourceDisplayNames(result.official_source_ids)
    : [];
  const cautionItems = result
    ? [...new Set([...result.missed_signals, ...result.next_actions])]
    : [];

  async function loadResult() {
    setStatus("loading");
    try {
      setResult((await practiceService.getResult(sessionId)).result);
      setStatus("success");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "연습 결과를 불러오지 못했습니다.");
      setStatus("error");
    }
  }

  useEffect(() => { void loadResult(); }, [sessionId]);

  return (
    <PageShell layout="report" step="계약 연습" title="대화 연습 평가서" description="대화에서 표현한 확인·문서화·보류 행동을 기준으로 복기합니다." showJourney={false}>
      <div className="stack">
        {status === "loading" && <LoadingState title="연습 결과를 불러오는 중" description="대화 근거와 최종 행동을 정리하고 있습니다." />}
        {status === "error" && <ErrorState title="연습 결과를 불러오지 못했습니다" description={errorMessage} onRetry={() => void loadResult()} />}
        {status === "success" && result && (
          <>
            <section className="practice-result-hero">
              <p>이번 대화의 대응 결과</p>
              <h2>{result.ending_title}</h2>
              <span>이 결과는 가상 대화에서 표현한 대응을 복기하며 실제 계약의 성사·피해·안전 여부를 판정하지 않습니다.</span>
            </section>
            <section className="practice-result-card">
              <h2>{result.feedback_label}</h2>
              <p>{result.feedback}</p>
            </section>
            <section className="practice-result-card">
              <h2>실제로 이렇게 말해보세요</h2>
              <p>“{result.practice_phrase}”</p>
            </section>
            <ResultList title="행동 지침 3줄 요약" items={result.action_summary} emptyText="추가 행동 지침이 없습니다." />
            <div className="practice-result-grid">
              <ResultList title="추가로 조심해야 할 부분" items={cautionItems} emptyText="추가로 안내할 주의사항이 없습니다." />
              <ResultList title="다른 표현 예시" items={result.recommended_phrases} emptyText="추가 권장 문장이 없습니다." />
            </div>
            <section className="practice-source-card">
              <h2>연결된 공식 근거</h2>
              <p>이번 연습의 확인 행동과 연결된 법령·공식자료입니다.</p>
              {officialSourceNames.length > 0 ? (
                <ul>{officialSourceNames.map((sourceName) => <li key={sourceName}>{sourceName}</li>)}</ul>
              ) : <p>연결된 공식 근거가 없습니다.</p>}
            </section>
            <div className="page-actions">
              <Link className="text-link" to={`/practice/scenarios/${result.scenario_id}`}>같은 상황 다시 연습</Link>
              <Link className="button-link" to="/practice">다른 상황 선택</Link>
            </div>
          </>
        )}
      </div>
    </PageShell>
  );
}
