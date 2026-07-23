import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { EmptyState, ErrorState, LoadingState } from "../../components/feedback/AsyncState";
import { PageShell } from "../../components/layout/PageShell";
import { practiceService } from "../../services/practiceService";
import type { PracticeScenarioSummaryDto } from "../../types/api";
import { practiceMissionForScenario } from "./practiceMissionCatalog";

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
    <PageShell layout="workspace" step="계약 연습" title="계약 상황을 미리 연습해 보세요" description="확인할 내용을 자신의 말로 질문하고, 결정 전에 보류하는 방법을 연습합니다." showJourney={false}>
      <div className="stack">
        <div className="practice-safety-note">
          <strong>실제 계약 결과와 분리된 연습입니다.</strong>
          <p>점수나 안전 판정 없이, 직접 확인한 행동과 놓친 확인 항목을 복기합니다.</p>
        </div>
        {status === "loading" && <LoadingState title="연습 목록을 불러오는 중" description="연습 상황을 확인하고 있습니다." />}
        {status === "error" && <ErrorState title="연습 목록을 불러오지 못했습니다" description={errorMessage} onRetry={() => void loadScenarios()} />}
        {status === "success" && scenarios.length === 0 && <EmptyState title="현재 이용할 수 있는 연습이 없습니다" description="승인된 시나리오가 준비되면 이곳에 표시됩니다." />}
        {status === "success" && scenarios.length > 0 && (
          <section className="practice-grid" aria-label="연습 시나리오 목록">
            {scenarios.map((scenario) => (
              <PracticeScenarioCard key={scenario.scenario_id} scenario={scenario} />
            ))}
          </section>
        )}
        <Link className="text-link" to="/contracts">내 계약으로 돌아가기</Link>
      </div>
    </PageShell>
  );
}

function PracticeScenarioCard({ scenario }: { scenario: PracticeScenarioSummaryDto }) {
  const mission = practiceMissionForScenario(scenario.scenario_id);
  const missionSummary = mission.targetCount === null
    ? "확인할 내용 살펴보기"
    : `약 3분 · 확인 행동 ${mission.targetCount}개`;

  return (
    <article className="practice-scenario-card">
      <h2>{scenario.title}</h2>
      <p>{mission.description}</p>
      <p className="practice-meta">{missionSummary}</p>
      <Link className="text-link" to={`/practice/scenarios/${scenario.scenario_id}`}>상황 확인하기</Link>
    </article>
  );
}
