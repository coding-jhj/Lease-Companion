import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { EmptyState, ErrorState, LoadingState } from "../../components/feedback/AsyncState";
import { PageShell } from "../../components/layout/PageShell";
import {
  PriorityGroups,
  cannotJudgeNow,
  displayPriorityForUrgency,
  type DisplayPriority,
} from "../../features/judgment-results/PriorityGroups";
import { DamagePatternTable } from "../../features/damage-patterns/DamagePatternTable";
import { ReportPrintSheet } from "../../features/result-report/ReportPrintSheet";
import { buildActionFirstItems } from "../../features/result-report/actionFirstViewModel";
import { SpecialClauseReviewSection } from "../../features/special-clauses/SpecialClauseReviewSection";
import { mvpService } from "../../services/mvpService";
import type {
  JudgmentGuidanceDto,
  JudgmentResultDto,
  RuleGuidanceDto,
  RuleResultDto,
  StageGuidanceDto,
  DamagePatternComparisonDto,
  SpecialClauseGuidanceDto,
  SpecialClauseReviewDto,
} from "../../types/api";
import { contractIdFromRoute } from "../../utils/contractId";

const priorities: DisplayPriority[] = ["반드시 확인", "확인 권장", "일반 확인"];

function actionHeroTitle(stage: StageGuidanceDto["contract_context"]["contract_stage"] | undefined, count: number) {
  if (stage === "계약금 입금 전") return `계약금을 보내기 전에 ${count}가지를 먼저 확인해 주세요`;
  if (stage === "계약 직후") return `계약 직후 ${count}가지를 차례로 확인해 주세요`;
  return `서명하기 전에 ${count}가지를 먼저 확인해 주세요`;
}

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
  const [damagePatterns, setDamagePatterns] = useState<DamagePatternComparisonDto[]>([]);
  const [specialClauseReviews, setSpecialClauseReviews] = useState<SpecialClauseReviewDto[]>([]);
  const [specialClauseGuidance, setSpecialClauseGuidance] = useState<SpecialClauseGuidanceDto[]>([]);
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
      setDamagePatterns(run.result?.damage_patterns ?? []);
      setSpecialClauseReviews(run.result?.special_clause_reviews ?? []);
      setSpecialClauseGuidance(run.generation_result?.special_clause_items ?? []);
      setGenerationFailed(run.generation_status === "failed");
      setStatus("success");
    } catch {
      setErrorMessage("확인 결과를 불러오지 못했습니다. 저장된 계약 정보는 변경되지 않았습니다. 다시 시도해 주세요.");
      setStatus("error");
    }
  }

  useEffect(() => { void loadReport(); }, [contractId, analysisRunId]);

  const allResults = [...items, ...judgments];
  const userFacingResults = judgments.length > 0 ? judgments : items;
  // v1.9에서 J10/J11이 명확성 판정의 canonical 결과다. 이전 저장 결과에
  // legacy R08/R09 안내가 함께 있어도 서로 모순된 수정 요청을 다시 노출하지 않는다.
  const canonicalJudgmentIds = new Set(judgments.map((item) => item.judgment_id));
  const compatibleRuleGuidance = ruleGuidance.filter((item) => !(
    (item.rule_id === "R08" && canonicalJudgmentIds.has("J10"))
    || (item.rule_id === "R09" && canonicalJudgmentIds.has("J11"))
  ));
  const allGuidance = [...compatibleRuleGuidance, ...judgmentGuidance];
  // 같은 항목을 "먼저 할 일"과 "왜 확인해야 하나요?"로 두 번 보여주지 않는다.
  // 시점·질문·정리된 설명을 확인 항목 카드 하나에 합쳐 전달한다.
  const actionFirstItems = buildActionFirstItems(userFacingResults, allGuidance, stageGuidance);
  const actionById = new Map(actionFirstItems.map((item) => [item.id, item]));
  // 상단 요약 개수는 하단 그룹과 같은 기준으로 센다: "지금 판단할 수 없는 항목"
  // (확인 불가·적용 제외·외부데이터 미연결)은 우선순위 그룹에서 빠지므로 카운트에서도 제외한다.
  const actionableResults = userFacingResults.filter((item) => !cannotJudgeNow(item));
  const counts = Object.fromEntries(priorities.map((priority) => [
    priority,
    actionableResults.filter((item) => displayPriorityForUrgency(item.urgency) === priority).length,
  ])) as Record<DisplayPriority, number>;
  const firstPriority = priorities.find((priority) => counts[priority] > 0);
  function printReport() {
    const previousTitle = document.title;
    document.title = `내_계약_확인_결과_계약_${contractId}`;
    window.print();
    document.title = previousTitle;
  }

  return (
    <PageShell layout="report" step="6 / 7" title="내 계약 확인 결과" description="가장 먼저 확인할 내용과 상대방에게 직접 확인할 내용을 순서대로 살펴보세요.">
      <div className="stack">
        {status === "loading" && <LoadingState title="확인 결과를 불러오는 중" description="항목별 확인 우선순위를 정리하고 있습니다." />}
        {status === "error" && <ErrorState title="확인 결과를 불러오지 못했습니다" description={errorMessage} onRetry={() => void loadReport()} />}
        {status === "success" && generationFailed && (
          <p className="notice" role="alert">확인 결과는 준비됐지만 쉬운 설명을 만들지 못했습니다. 확인 항목과 문서 근거는 그대로 볼 수 있습니다.</p>
        )}
        {status === "success" && allResults.length === 0 && <EmptyState title="아직 준비된 확인 결과가 없습니다" description="문서에서 읽은 내용을 확인하고 결과 준비를 마치면 표시됩니다." />}
        {status === "success" && allResults.length > 0 && (
          <>
            <section className="report-hero" aria-labelledby="report-guide-title">
              <div>
                <h2 id="report-guide-title">
                  {actionHeroTitle(stageGuidance?.contract_context.contract_stage, actionFirstItems.length)}
                </h2>
                <span>확인 항목은 문서와 상대방에게 확인할 순서이며, 계약 진행 여부를 대신 결정하지 않습니다.</span>
                <ul className="report-hero__counts" aria-label="확인 우선순위 전체 개수">
                  {priorities.map((priority) => (
                    <li data-priority={priority} key={priority}>
                      <span>{priority}</span>
                      <strong>{counts[priority]}<em>개</em></strong>
                    </li>
                  ))}
                </ul>
              </div>
              <button className="report-hero__print" type="button" onClick={printReport}>확인 결과 PDF 저장</button>
            </section>
            {createPortal(<ReportPrintSheet contractId={contractId} patterns={damagePatterns} actionResults={userFacingResults} results={allResults} guidance={allGuidance} specialClauseReviews={specialClauseReviews} specialClauseGuidance={specialClauseGuidance} stageGuidance={stageGuidance} />, document.body)}
            {damagePatterns.length > 0 && (
              <section className="damage-reference-section stack" aria-label="금전 피해 유형 비교">
                <DamagePatternTable items={damagePatterns} />
              </section>
            )}
            <section className="report-items-section stack" aria-labelledby="report-items-title">
              <div className="section-heading">
                <h2 id="report-items-title">확인 항목</h2>
                <p>문서와 상대방에게 확인할 내용을 우선순위별로 정리합니다</p>
              </div>
              <PriorityGroups
                items={userFacingResults}
                idPrefix="all-results-priority"
                focusPriority={firstPriority}
                actionById={actionById}
              />
              <SpecialClauseReviewSection reviews={specialClauseReviews} guidance={specialClauseGuidance} generationFailed={generationFailed} />
            </section>
          </>
        )}
        <button type="button" onClick={() => navigate(`/contracts/${contractId}`)}>이제 할 일 확인하기</button>
      </div>
    </PageShell>
  );
}
