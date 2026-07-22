import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ErrorState, LoadingState } from "../../components/feedback/AsyncState";
import { PageShell } from "../../components/layout/PageShell";
import { practiceService } from "../../services/practiceService";
import type { PracticeResultDto } from "../../types/api";

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
    <PageShell layout="report" step="계약 연습" title="연습 결과 복기" description="점수가 아니라 실제로 표현한 확인 행동, 놓친 신호, 다음에 사용할 문장을 확인합니다." showJourney={false}>
      <div className="stack">
        {status === "loading" && <LoadingState title="연습 결과를 불러오는 중" description="대화 근거와 최종 행동을 정리하고 있습니다." />}
        {status === "error" && <ErrorState title="연습 결과를 불러오지 못했습니다" description={errorMessage} onRetry={() => void loadResult()} />}
        {status === "success" && result && (
          <>
            <section className="practice-result-hero">
              <p>내가 선택한 최종 행동</p>
              <h2>{result.selected_action ?? "선택하지 않음"}</h2>
              <span>이 결과는 가상 연습 복기이며 실제 계약의 안전·위험을 판정하지 않습니다.</span>
            </section>
            <div className="practice-result-grid">
              <ResultList title="잘 확인한 행동" items={result.confirmed_actions} emptyText="대화에서 명확히 확인된 행동이 없습니다." />
              <ResultList title="놓친 확인 신호" items={result.missed_signals} emptyText="이번 연습에서 놓친 확인 신호가 없습니다." />
              <ResultList title="다음에 말할 문장" items={result.recommended_phrases} emptyText="추가 권장 문장이 없습니다." />
              <ResultList title="다음 행동" items={result.next_actions} emptyText="추가 행동이 없습니다." />
            </div>
            <section className="practice-source-card">
              <h2>연결된 공식 근거</h2>
              <p>현재 API는 공식자료 식별자를 제공합니다. 실제 자료 제목과 원문 링크 연결은 후속 작업에서 보강합니다.</p>
              {result.official_source_ids.length > 0 ? (
                <ul>{result.official_source_ids.map((sourceId) => <li key={sourceId}>{sourceId}</li>)}</ul>
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
