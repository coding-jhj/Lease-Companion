import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ErrorState, LoadingState } from "../../components/feedback/AsyncState";
import { PageShell } from "../../components/layout/PageShell";
import { AnalysisTimeline, type AnalysisStage } from "../../features/analysis-progress/AnalysisTimeline";
import { mvpService } from "../../services/mvpService";
import type { AnalysisRunDetailDto, AsyncRunStatus } from "../../types/api";
import { contractIdFromRoute } from "../../utils/contractId";
import { PollTimeoutError, pollUntilTerminal } from "../../utils/pollUntilTerminal";

type PageStatus = AsyncRunStatus | "timeout";
type RetryMode = "new" | "resume";

export function AnalysisProgressPage() {
  const { contractId: routeContractId } = useParams();
  const contractId = contractIdFromRoute(routeContractId);
  const navigate = useNavigate();
  const [status, setStatus] = useState<PageStatus>("pending");
  const [activeStage, setActiveStage] = useState<AnalysisStage>("request");
  const [analysisRunId, setAnalysisRunId] = useState("");
  const [error, setError] = useState("");
  const activePoll = useRef<AbortController | null>(null);
  const startPromise = useRef<Promise<AnalysisRunDetailDto> | null>(null);
  const startContractId = useRef<number | null>(null);
  const retryMode = useRef<RetryMode>("new");

  async function pollRun(initialRun: AnalysisRunDetailDto, controller: AbortController) {
    setAnalysisRunId(initialRun.analysis_run_id);
    const run = await pollUntilTerminal({
      initialValue: initialRun,
      poll: () => mvpService.getAnalysisRun(contractId, initialRun.analysis_run_id, controller.signal),
      signal: controller.signal,
      onUpdate: (current) => {
        if (current.status === "pending" || current.status === "running") {
          setStatus(current.status);
          setActiveStage(current.status === "pending" ? "request" : "analysis");
        } else if (current.status === "completed"
          && (current.generation_status === null
            || current.generation_status === "pending"
            || current.generation_status === "running")) {
          setStatus("running");
          setActiveStage("generation");
        }
      },
      isTerminal: (current) => current.status === "failed"
        || (current.status === "completed"
          && (current.generation_status === "completed" || current.generation_status === "failed")),
    });

    if (run.status === "failed") {
      startPromise.current = null;
      retryMode.current = "new";
      setStatus("failed");
      setActiveStage("analysis");
      setError(run.error ?? "확인 결과를 준비하지 못했습니다.");
      return;
    }
    retryMode.current = "resume";
    setStatus("completed");
    setActiveStage("complete");
  }

  async function startNewAnalysis(forceNew = false) {
    activePoll.current?.abort();
    const controller = new AbortController();
    activePoll.current = controller;
    retryMode.current = "new";
    if (startContractId.current !== contractId) {
      startContractId.current = contractId;
      startPromise.current = null;
    }
    if (forceNew) startPromise.current = null;
    setError("");
    setStatus("pending");
    setActiveStage("request");

    try {
      startPromise.current ??= mvpService.startAnalysis(contractId);
      const run = await startPromise.current;
      if (controller.signal.aborted) return;
      retryMode.current = "resume";
      await pollRun(run, controller);
    } catch (caught) {
      if (controller.signal.aborted || (caught instanceof DOMException && caught.name === "AbortError")) return;
      if (caught instanceof PollTimeoutError) {
        retryMode.current = "resume";
        setStatus("timeout");
        setError(caught.message);
        return;
      }
      startPromise.current = null;
      setStatus("failed");
      setActiveStage("request");
      setError(caught instanceof Error ? caught.message : "확인 결과를 준비하지 못했습니다.");
    }
  }

  async function resumeAnalysis() {
    if (!analysisRunId) {
      await startNewAnalysis();
      return;
    }

    activePoll.current?.abort();
    const controller = new AbortController();
    activePoll.current = controller;
    retryMode.current = "resume";
    setError("");
    setStatus("pending");

    try {
      const run = await mvpService.getAnalysisRun(contractId, analysisRunId, controller.signal);
      if (controller.signal.aborted) return;
      await pollRun(run, controller);
    } catch (caught) {
      if (controller.signal.aborted || (caught instanceof DOMException && caught.name === "AbortError")) return;
      setStatus(caught instanceof PollTimeoutError ? "timeout" : "failed");
      setError(caught instanceof Error ? caught.message : "결과 준비 상태를 다시 확인하지 못했습니다.");
    }
  }

  function retry() {
    return retryMode.current === "resume" ? resumeAnalysis() : startNewAnalysis(true);
  }

  useEffect(() => {
    void startNewAnalysis();
    return () => activePoll.current?.abort();
  }, [contractId]);

  const title = status === "completed"
    ? "확인 결과 준비 완료"
    : status === "running"
      ? "계약 확인 결과를 준비하고 있어요"
      : status === "timeout"
        ? "결과 준비 상태 확인이 지연되고 있어요"
        : "결과 준비를 기다리고 있어요";

  return (
    <PageShell step="6 / 8" title={title} description="규칙 판정과 공식 근거를 정리합니다. 종합 안전 점수는 제공하지 않습니다.">
      <div className="stack">
        <AnalysisTimeline
          activeStage={activeStage}
          hasError={status === "failed"}
          delayed={status === "timeout"}
        />
        {status === "pending" && <LoadingState title="결과 준비 대기 중" description="서버에서 결과 준비를 시작하고 있습니다." />}
        {status === "running" && <LoadingState title="확인 결과 준비 중" description="완료될 때까지 실제 준비 상태를 확인하고 있습니다." />}
        {status === "failed" && <ErrorState title="확인 결과를 준비하지 못했습니다" description={error} onRetry={() => void retry()} />}
        {status === "timeout" && <ErrorState title="결과 준비 상태 확인이 지연되고 있습니다" description={error} onRetry={() => void retry()} />}
        <button type="button" disabled={status !== "completed"} onClick={() => navigate(`/contracts/${contractId}/report?analysisRunId=${encodeURIComponent(analysisRunId)}`)}>{status === "completed" ? "확인 결과 보기" : "결과 준비 중…"}</button>
      </div>
    </PageShell>
  );
}
