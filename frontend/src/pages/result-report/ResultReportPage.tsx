import { useEffect, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { EmptyState, ErrorState, LoadingState } from "../../components/feedback/AsyncState";
import { PageShell } from "../../components/layout/PageShell";
import { PriorityGroups } from "../../features/judgment-results/PriorityGroups";
import { GenerationGuidance } from "../../features/question-cards/GenerationGuidance";
import { StageGuidance } from "../../features/question-cards/StageGuidance";
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

  const coreRules = items.filter((item) => Number(item.rule_id.slice(1)) <= 10);
  const automatedExpansion = items.filter((item) => [11, 12, 13, 14, 15, 17, 18, 19].includes(Number(item.rule_id.slice(1))));
  const checklistFirst = items.filter((item) => [16, 23, 24].includes(Number(item.rule_id.slice(1))));
  const externalPending = items.filter((item) => [20, 21, 22].includes(Number(item.rule_id.slice(1))));

  return (
    <PageShell layout="report" step="7 / 8" title="계약 확인 리포트" description="항목별 확인 필요성과 다음 질문을 살펴보세요.">
      <div className="stack">
        {status === "loading" && <LoadingState title="리포트를 불러오는 중" description="항목별 확인 우선순위를 정리하고 있습니다." />}
        {status === "error" && <ErrorState title="리포트를 불러오지 못했습니다" description={errorMessage} onRetry={() => void loadReport()} />}
        {status === "success" && generationFailed && (
          <p className="notice" role="alert">규칙 판정은 정상이며 안내 생성에 실패했습니다.</p>
        )}
        {status === "success" && items.length === 0 && <EmptyState title="아직 생성된 리포트가 없습니다" description="추출값 확인과 분석을 완료하면 결과가 표시됩니다." />}
        {status === "success" && items.length > 0 && (
          <div className="report-grid">
            <div className="report-results-column stack">
        {status === "success" && coreRules.length > 0 && (
          <section aria-labelledby="rule-results-title">
            <h2 id="rule-results-title">기존 핵심 규칙 R01~R10</h2>
            <PriorityGroups idPrefix="rule-priority" items={coreRules} />
          </section>
        )}
        {status === "success" && automatedExpansion.length > 0 && (
          <section aria-labelledby="expanded-rule-results-title">
            <h2 id="expanded-rule-results-title">1차 MVP 확장 판정</h2>
            <p className="section-description">확인된 문서·사용자 입력값으로 계산하거나 판정합니다. 값이 없으면 확인 불가로 표시합니다.</p>
            <PriorityGroups idPrefix="expanded-rule-priority" items={automatedExpansion} />
          </section>
        )}
        {status === "success" && checklistFirst.length > 0 && (
          <section aria-labelledby="checklist-rule-results-title">
            <h2 id="checklist-rule-results-title">질문·체크리스트 우선 확인</h2>
            <p className="section-description">현재 문서만으로 단정하지 않고 당사자와 공식 자료에 확인할 질문으로 제공합니다.</p>
            <PriorityGroups idPrefix="checklist-rule-priority" items={checklistFirst} />
          </section>
        )}
        {status === "success" && externalPending.length > 0 && (
          <section aria-labelledby="external-rule-results-title">
            <h2 id="external-rule-results-title">외부 데이터 연결 후 자동화</h2>
            <p className="section-description">외부 데이터가 아직 연결되지 않은 항목이며 현재는 확인 불가와 직접 확인 행동을 제공합니다.</p>
            <PriorityGroups idPrefix="external-rule-priority" items={externalPending} />
          </section>
        )}
        {status === "success" && judgments.length > 0 && (
          <section aria-labelledby="judgment-results-title">
            <h2 id="judgment-results-title">J01~J12 계약 판정</h2>
            <p className="section-description">핵심 규칙 결과와 별도로, 계약서와 관련 문서를 12개 판정 항목으로 확인한 결과입니다.</p>
            <PriorityGroups idPrefix="judgment-priority" items={judgments} />
          </section>
        )}
            </div>
            <aside className="report-guidance-column stack" aria-label="질문과 행동 안내">
              {ruleGuidance.length > 0 && (
                <GenerationGuidance headingId="rule-guidance-title" title="R01~R24 규칙 기반 질문과 행동" items={ruleGuidance} />
              )}
              {judgmentGuidance.length > 0 && (
                <GenerationGuidance headingId="judgment-guidance-title" title="J01~J12 판정 기반 질문과 행동" items={judgmentGuidance} />
              )}
              {stageGuidance && <StageGuidance guidance={stageGuidance} />}
              <ResultFeedback contractId={contractId} />
            </aside>
          </div>
        )}
        <button type="button" onClick={() => navigate(`/contracts/${contractId}`)}>체크리스트로 이동</button>
      </div>
    </PageShell>
  );
}
