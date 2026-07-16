import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { EmptyState, ErrorState, LoadingState } from "../../components/feedback/AsyncState";
import { PageShell } from "../../components/layout/PageShell";
import { mvpService } from "../../services/mvpService";
import type { ContractSummary } from "../../types/api";

export function DashboardPage() {
  const [contracts, setContracts] = useState<ContractSummary[]>([]);
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [errorMessage, setErrorMessage] = useState("");

  async function loadContracts() {
    setStatus("loading");
    try {
      setContracts(await mvpService.getContracts());
      setStatus("success");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "계약 목록을 불러오지 못했습니다.");
      setStatus("error");
    }
  }

  useEffect(() => { void loadContracts(); }, []);

  return (
    <PageShell step="2 / 8" title="내 계약" description="진행 중인 계약을 다시 열거나 새 계약 확인을 시작하세요.">
      <div className="stack">
        {status === "loading" && <LoadingState title="계약 목록을 불러오는 중" description="저장된 계약 건을 확인하고 있습니다." />}
        {status === "error" && <ErrorState title="계약 목록을 불러오지 못했습니다" description={errorMessage} onRetry={() => void loadContracts()} />}
        {status === "success" && contracts.length === 0 && <EmptyState title="아직 저장된 계약이 없습니다" description="새 계약을 만들어 확인을 시작해 보세요." />}
        {status === "success" && contracts.map((contract) => (
          <article className="contract-card" key={contract.contractId}>
            <strong>{contract.title}</strong><span>{contract.stage} · {contract.updatedAt}</span>
            <div className="card-actions">
              <Link className="text-link" to={`/contracts/${contract.contractId}`}>계약 상세 보기</Link>
              <Link className="text-link text-link--report" to={`/contracts/${contract.contractId}/report`}>기존 리포트 다시 보기</Link>
            </div>
          </article>
        ))}
        <Link className="button-link" to="/contracts/new">새 계약 만들기</Link>
      </div>
    </PageShell>
  );
}
