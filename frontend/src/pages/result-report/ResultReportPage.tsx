import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { EmptyState, ErrorState, LoadingState } from "../../components/feedback/AsyncState";
import { PageShell } from "../../components/layout/PageShell";
import { PriorityGroups } from "../../features/judgment-results/PriorityGroups";
import { mvpService } from "../../services/mvpService";
import type { RuleResultDto } from "../../types/api";
import { contractIdFromRoute } from "../../utils/contractId";

export function ResultReportPage() {
  const { contractId: routeContractId } = useParams();
  const contractId = contractIdFromRoute(routeContractId);
  const navigate = useNavigate();
  const [items, setItems] = useState<RuleResultDto[]>([]);
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [errorMessage, setErrorMessage] = useState("");

  async function loadReport() {
    setStatus("loading");
    try {
      setItems((await mvpService.getAnalysisResult(contractId)).results);
      setStatus("success");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "리포트를 불러오지 못했습니다.");
      setStatus("error");
    }
  }

  useEffect(() => { void loadReport(); }, [contractId]);

  return (
    <PageShell step="7 / 8" title="계약 확인 리포트" description="항목별 확인 필요성과 다음 질문을 살펴보세요.">
      <div className="stack">
        {status === "loading" && <LoadingState title="리포트를 불러오는 중" description="항목별 확인 우선순위를 정리하고 있습니다." />}
        {status === "error" && <ErrorState title="리포트를 불러오지 못했습니다" description={errorMessage} onRetry={() => void loadReport()} />}
        {status === "success" && items.length === 0 && <EmptyState title="아직 생성된 리포트가 없습니다" description="추출값 확인과 분석을 완료하면 결과가 표시됩니다." />}
        {status === "success" && items.length > 0 && <PriorityGroups items={items} />}
        <button type="button" onClick={() => navigate(`/contracts/${contractId}`)}>체크리스트로 이동</button>
      </div>
    </PageShell>
  );
}
