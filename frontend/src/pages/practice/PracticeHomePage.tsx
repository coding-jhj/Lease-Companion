import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { EmptyState, ErrorState, LoadingState } from "../../components/feedback/AsyncState";
import { PageShell } from "../../components/layout/PageShell";
import { practiceService } from "../../services/practiceService";
import type { PracticeScenarioSummaryDto } from "../../types/api";

export function PracticeHomePage() {
  const [scenarios, setScenarios] = useState<PracticeScenarioSummaryDto[]>([]);
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [errorMessage, setErrorMessage] = useState("");

  async function loadScenarios() {
    setStatus("loading");
    try {
      setScenarios(await practiceService.listScenarios());
      setStatus("success");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "연습 목록을 불러오지 못했습니다.");
      setStatus("error");
    }
  }

  useEffect(() => { void loadScenarios(); }, []);

  return (
    <PageShell layout="workspace" step="계약 연습" title="계약 대화 연습" description="가상의 임대인·공인중개사와 대화하며 확인 질문과 보류 행동을 연습합니다." showJourney={false}>
      <div className="stack">
        <div className="practice-safety-note">
          <strong>실제 계약 분석이 아닌 가상 연습입니다.</strong>
          <p>점수나 안전 판정 없이, 직접 확인한 행동과 놓친 확인 항목을 복기합니다.</p>
        </div>
        {status === "loading" && <LoadingState title="연습 목록을 불러오는 중" description="승인된 합성 시나리오를 확인하고 있습니다." />}
        {status === "error" && <ErrorState title="연습 목록을 불러오지 못했습니다" description={errorMessage} onRetry={() => void loadScenarios()} />}
        {status === "success" && scenarios.length === 0 && <EmptyState title="현재 이용할 수 있는 연습이 없습니다" description="승인된 시나리오가 준비되면 이곳에 표시됩니다." />}
        {status === "success" && scenarios.length > 0 && (
          <section className="practice-grid" aria-label="연습 시나리오 목록">
            {scenarios.map((scenario) => (
              <article className="practice-scenario-card" key={scenario.scenario_id}>
                <div className="practice-labels">
                  {scenario.always_show_labels.map((label) => <span key={label}>{label}</span>)}
                </div>
                <h2>{scenario.title}</h2>
                <dl className="practice-meta">
                  <div><dt>상대 역할</dt><dd>{scenario.role}</dd></div>
                  <div><dt>난이도</dt><dd>{scenario.difficulty}</dd></div>
                  <div><dt>계약 단계</dt><dd>{scenario.contract_stage}</dd></div>
                </dl>
                <Link className="button-link" to={`/practice/scenarios/${scenario.scenario_id}`}>상황 먼저 보기</Link>
              </article>
            ))}
          </section>
        )}
        <Link className="text-link" to="/contracts">내 계약으로 돌아가기</Link>
      </div>
    </PageShell>
  );
}
