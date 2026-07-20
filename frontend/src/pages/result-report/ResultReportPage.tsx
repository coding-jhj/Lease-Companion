import { useEffect, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { EmptyState, ErrorState, LoadingState } from "../../components/feedback/AsyncState";
import { PageShell } from "../../components/layout/PageShell";
import {
  PriorityGroups,
  cannotJudgeNow,
  displayPriorityForUrgency,
  type DisplayPriority,
} from "../../features/judgment-results/PriorityGroups";
import { DefenseActionHub } from "../../features/question-cards/DefenseActionHub";
import { ResultFeedback } from "../../features/result-feedback/ResultFeedback";
import { mvpService } from "../../services/mvpService";
import type {
  JudgmentGuidanceDto,
  JudgmentResultDto,
  RuleGuidanceDto,
  RuleResultDto,
  StageGuidanceDto,
} from "../../types/api";
import { contractIdFromRoute } from "../../utils/contractId";

const priorities: DisplayPriority[] = ["반드시 확인", "확인 권장", "일반 확인"];

export function ResultReportPage() {
  const { contractId: routeContractId } = useParams();
  const contractId = contractIdFromRoute(routeContractId);
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const analysisRunId = searchParams.get("analysisRunId") ?? undefined;
  const [items, setItems] = useState<RuleResultDto[]>([]);
  const [judgments, setJudgments] = useState<JudgmentResultDto[]>([]);
  const [ruleGuidance, setRuleGuidance] = useState<RuleGuidanceDto[]>([]);
  const [judgmentGuidance, setJudgmentGuidance] = useState<JudgmentGuidanceDto[]>([]);
  const [stageGuidance, setStageGuidance] = useState<StageGuidanceDto | null>(null);
  const [generationFailed, setGenerationFailed] = useState(false);
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [errorMessage, setErrorMessage] = useState("");

  async function loadReport() {
    setStatus("loading");
    try {
      const run = await mvpService.getAnalysisDetail(contractId, analysisRunId);
      setItems(run.result?.results ?? []);
      setJudgments(run.result?.judgments ?? []);
      setRuleGuidance(run.generation_result?.items ?? []);
      setJudgmentGuidance(run.generation_result?.judgment_items ?? []);
      setStageGuidance(run.generation_result?.stage_guidance ?? null);
      setGenerationFailed(run.generation_status === "failed");
      setStatus("success");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "리포트를 불러오지 못했습니다.");
      setStatus("error");
    }
  }

  useEffect(() => { void loadReport(); }, [contractId, analysisRunId]);

  const allResults = [...items, ...judgments];
  const userFacingResults = judgments.length > 0 ? judgments : items;
  const usesJudgmentSummary = judgments.length > 0;
  const allGuidance = [...ruleGuidance, ...judgmentGuidance];
  // 상단 요약 개수는 하단 그룹과 같은 기준으로 센다: "지금 판단할 수 없는 항목"
  // (확인 불가·적용 제외·외부데이터 미연결)은 우선순위 그룹에서 빠지므로 카운트에서도 제외한다.
  const actionableResults = userFacingResults.filter((item) => !cannotJudgeNow(item));
  const counts = Object.fromEntries(priorities.map((priority) => [
    priority,
    actionableResults.filter((item) => displayPriorityForUrgency(item.urgency) === priority).length,
  ])) as Record<DisplayPriority, number>;
  const firstPriority = priorities.find((priority) => counts[priority] > 0);

  return (
    <PageShell layout="report" step="7 / 8" title="임차인 방어 리포트" description="판정 자체보다 무엇을 확인하고 어떻게 행동할지 차근차근 살펴보세요.">
      <div className="stack">
        {status === "loading" && <LoadingState title="리포트를 불러오는 중" description="항목별 확인 우선순위를 정리하고 있습니다." />}
        {status === "error" && <ErrorState title="리포트를 불러오지 못했습니다" description={errorMessage} onRetry={() => void loadReport()} />}
        {status === "success" && generationFailed && (
          <p className="notice" role="alert">규칙 판정은 정상이며 안내 생성에 실패했습니다. 확인 결과는 그대로 볼 수 있습니다.</p>
        )}
        {status === "success" && allResults.length === 0 && <EmptyState title="아직 생성된 리포트가 없습니다" description="추출값 확인과 분석을 완료하면 결과가 표시됩니다." />}
        {status === "success" && allResults.length > 0 && (
          <>
            <section className="report-hero" aria-labelledby="report-guide-title">
              <div>
                <p>천천히 하나씩 확인하면 됩니다</p>
                <h2 id="report-guide-title">서두르지 않아도 괜찮아요.</h2>
                <span>이 리포트는 안전 여부를 단정하지 않고, 먼저 확인할 순서를 알려드립니다.</span>
              </div>
              {firstPriority && <a className="report-hero__link" href="#first-priority-group">가장 먼저 확인할 항목으로 이동</a>}
            </section>
            <section className="priority-summary" aria-label="확인 우선순위 전체 개수">
              {priorities.map((priority) => (
                <div data-priority={priority} key={priority}>
                  <span>{priority}</span>
                  <strong>{counts[priority]}개</strong>
                </div>
              ))}
            </section>
            <div className="report-grid">
              <section className="report-results-column stack" aria-labelledby="all-results-title">
                <div className="section-heading">
                  <p>
                    {usesJudgmentSummary
                      ? "내부 검사 결과의 중복을 빼고 계약에서 확인할 항목만 정리했습니다"
                      : "이전 분석의 핵심 규칙 결과를 정리했습니다"}
                  </p>
                  <h2 id="all-results-title">
                    {usesJudgmentSummary ? "12가지 계약 확인 결과" : "핵심 규칙 확인 결과"}
                  </h2>
                </div>
                <PriorityGroups
                  items={userFacingResults}
                  idPrefix="all-results-priority"
                  focusPriority={firstPriority}
                />
              </section>
              <aside className="report-guidance-column stack" aria-label="질문과 행동 안내">
                <DefenseActionHub results={allResults} guidance={allGuidance} stageGuidance={stageGuidance} />
                <ResultFeedback contractId={contractId} />
              </aside>
            </div>
          </>
        )}
        <button type="button" onClick={() => navigate(`/contracts/${contractId}`)}>저장된 체크리스트로 이동</button>
      </div>
    </PageShell>
  );
}
