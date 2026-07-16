import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { PageShell } from "../../components/layout/PageShell";
import { mvpService } from "../../services/mvpService";
import type { ContractSummary } from "../../types/api";

export function DashboardPage() {
  const [contracts, setContracts] = useState<ContractSummary[]>([]);
  useEffect(() => { void mvpService.getContracts().then(setContracts); }, []);

  return (
    <PageShell step="2 / 8" title="내 계약" description="진행 중인 계약을 다시 열거나 새 계약 확인을 시작하세요.">
      <div className="stack">
        {contracts.map((contract) => (
          <Link className="contract-card" to={`/contracts/${contract.contractId}`} key={contract.contractId}>
            <strong>{contract.title}</strong><span>{contract.stage} · {contract.updatedAt}</span>
          </Link>
        ))}
        <Link className="button-link" to="/contracts/new">새 계약 만들기</Link>
      </div>
    </PageShell>
  );
}
