import { useEffect, useRef, useState, type KeyboardEvent } from "react";
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
import { QuestionHub, StageActions } from "../../features/question-cards/DefenseActionHub";
import { ResultFeedback } from "../../features/result-feedback/ResultFeedback";
import { DamagePatternTable } from "../../features/damage-patterns/DamagePatternTable";
import { DetectedSignalSection } from "../../features/damage-patterns/DetectedSignalSection";
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

const TABS = [
  { key: "items", label: "확인 항목" },
  { key: "questions", label: "물어볼 말" },
  { key: "stages", label: "단계별 행동" },
] as const;

type TabKey = (typeof TABS)[number]["key"];

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
  const [tab, setTab] = useState<TabKey>("items");
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([]);

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
  const patternCounts = {
    signal: damagePatterns.filter((item) => item.status === "관련 확인 신호 있음").length,
    clear: damagePatterns.filter((item) => item.status === "제출 자료에서 관련 신호 미확인").length,
    unknown: damagePatterns.filter((item) => item.status === "자료 부족으로 확인 불가").length,
  };

  function printReport() {
    const previousTitle = document.title;
    document.title = `내_계약_확인_결과_계약_${contractId}`;
    window.print();
    document.title = previousTitle;
  }

  function moveTabFocus(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    const last = TABS.length - 1;
    let next = index;
    if (event.key === "ArrowRight") next = index === last ? 0 : index + 1;
    else if (event.key === "ArrowLeft") next = index === 0 ? last : index - 1;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = last;
    else return;
    event.preventDefault();
    setTab(TABS[next].key);
    tabRefs.current[next]?.focus();
  }

  return (
    <PageShell layout="report" step="7 / 8" title="내 계약 확인 결과" description="가장 먼저 확인할 내용과 상대방에게 물어볼 말을 순서대로 살펴보세요.">
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
            <div className="report-tabs" role="tablist" aria-label="확인 결과 보기 방식">
              {TABS.map((item, index) => (
                <button
                  className="report-tabs__tab"
                  type="button"
                  role="tab"
                  id={`report-tab-${item.key}`}
                  aria-selected={tab === item.key}
                  aria-controls={`report-panel-${item.key}`}
                  tabIndex={tab === item.key ? 0 : -1}
                  ref={(node) => { tabRefs.current[index] = node; }}
                  onClick={() => setTab(item.key)}
                  onKeyDown={(event) => moveTabFocus(event, index)}
                  key={item.key}
                >
                  {item.label}
                </button>
              ))}
            </div>
            {/* 탭을 옮겨도 펼쳐 둔 그룹·"더 보기" 상태가 풀리지 않도록 감추기만 한다. */}
            <div className="report-panel stack" role="tabpanel" id="report-panel-items" aria-labelledby="report-tab-items" hidden={tab !== "items"}>
              <PriorityGroups
                items={userFacingResults}
                idPrefix="all-results-priority"
                focusPriority={firstPriority}
                actionById={actionById}
              />
              <SpecialClauseReviewSection reviews={specialClauseReviews} guidance={specialClauseGuidance} generationFailed={generationFailed} />
            </div>
            <div className="report-panel" role="tabpanel" id="report-panel-questions" aria-labelledby="report-tab-questions" hidden={tab !== "questions"}>
              <QuestionHub results={allResults} guidance={allGuidance} stageGuidance={stageGuidance} />
            </div>
            <div className="report-panel" role="tabpanel" id="report-panel-stages" aria-labelledby="report-tab-stages" hidden={tab !== "stages"}>
              <StageActions results={allResults} guidance={allGuidance} stageGuidance={stageGuidance} />
            </div>
            {damagePatterns.length > 0 && (
              <section className="damage-reference-section stack" aria-labelledby="damage-reference-title">
                <div className="section-heading">
                  <h2 id="damage-reference-title">비슷한 상황에서 확인할 점</h2>
                </div>
                <DetectedSignalSection patterns={damagePatterns} guidance={allGuidance} />
                <details className="damage-table-fold">
                  <summary>
                    전체 비교표 보기 — 관련 확인 신호 {patternCounts.signal}건 · 관련 신호 미확인 {patternCounts.clear}건 · 자료 부족 {patternCounts.unknown}건
                  </summary>
                  <DamagePatternTable items={damagePatterns} />
                </details>
              </section>
            )}
            <details className="feedback-fold">
              <summary>리포트 의견 보내기</summary>
              <ResultFeedback contractId={contractId} />
            </details>
          </>
        )}
        <button type="button" onClick={() => navigate(`/contracts/${contractId}`)}>이제 할 일 확인하기</button>
      </div>
    </PageShell>
  );
}
