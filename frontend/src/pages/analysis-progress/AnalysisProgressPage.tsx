import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ErrorState, LoadingState } from "../../components/feedback/AsyncState";
import { PageShell } from "../../components/layout/PageShell";
import { mvpService } from "../../services/mvpService";
import type { AnalysisRunDetailDto, AsyncRunStatus } from "../../types/api";
import { contractIdFromRoute } from "../../utils/contractId";

const POLL_INTERVAL_MS = 1000;

export function AnalysisProgressPage() {
  const { contractId: routeContractId } = useParams();
  const contractId = contractIdFromRoute(routeContractId);
  const navigate = useNavigate();
  const [status, setStatus] = useState<AsyncRunStatus>("pending");
  const [analysisRunId, setAnalysisRunId] = useState("");
  const [error, setError] = useState("");
  const startPromise = useRef<Promise<AnalysisRunDetailDto> | null>(null);
  const pollGeneration = useRef(0);

  async function runAnalysis() {
    const generation = ++pollGeneration.current;
    setError("");
    setStatus("pending");
    try {
      startPromise.current ??= mvpService.startAnalysis(contractId);
      let run = await startPromise.current;
      setAnalysisRunId(run.analysis_run_id);
      while (run.status === "pending" || run.status === "running") {
        if (generation !== pollGeneration.current) return;
        setStatus(run.status);
        await new Promise((resolve) => window.setTimeout(resolve, POLL_INTERVAL_MS));
        run = await mvpService.getAnalysisRun(contractId, run.analysis_run_id);
      }
      if (generation !== pollGeneration.current) return;
      if (run.status === "failed") throw new Error(run.error ?? "계약 분석에 실패했습니다.");
      setStatus("completed");
    } catch (caught) {
      setStatus("failed");
      setError(caught instanceof Error ? caught.message : "계약 분석에 실패했습니다.");
      startPromise.current = null;
    }
  }

  useEffect(() => {
    void runAnalysis();
    return () => { pollGeneration.current += 1; };
  }, [contractId]);

  const title = status === "completed" ? "분석 완료" : status === "running" ? "계약 내용을 분석하고 있어요" : "분석 시작을 기다리고 있어요";

  return (
    <PageShell step="6 / 8" title={title} description="규칙 판정과 공식 근거를 정리합니다. 종합 안전 점수는 제공하지 않습니다.">
      <div className="stack">
        {status === "pending" && <LoadingState title="분석 대기 중" description="서버에서 분석 작업을 준비하고 있습니다." />}
        {status === "running" && <LoadingState title="분석 실행 중" description="완료될 때까지 실제 분석 상태를 확인하고 있습니다." />}
        {status === "failed" && <ErrorState title="분석을 완료하지 못했습니다" description={error} onRetry={() => void runAnalysis()} />}
        <button type="button" disabled={status !== "completed"} onClick={() => navigate(`/contracts/${contractId}/report?analysisRunId=${encodeURIComponent(analysisRunId)}`)}>{status === "completed" ? "리포트 보기" : "분석 중…"}</button>
      </div>
    </PageShell>
  );
}
