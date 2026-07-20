import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { EmptyState, ErrorState, LoadingState } from "../../components/feedback/AsyncState";
import { PageShell } from "../../components/layout/PageShell";
import { mvpService } from "../../services/mvpService";
import type { ContractSummaryDto } from "../../types/api";

function ContractCard({ contract }: { contract: ContractSummaryDto }) {
  return (
    <article className="contract-card">
      <strong>{contract.title}</strong>
      <span>{contract.contract_stage ?? "상황 입력 전"} · {new Date(contract.created_at).toLocaleDateString("ko-KR")}</span>
      <div className="card-actions">
        <Link className="text-link" to={"/contracts/" + contract.id}>계약 상세 보기</Link>
        <Link className="text-link text-link--report" to={"/contracts/" + contract.id + "/report"}>기존 리포트 다시 보기</Link>
      </div>
    </article>
  );
}

function ContractGroup({ title, contracts }: { title: string; contracts: ContractSummaryDto[] }) {
  if (contracts.length === 0) return null;
  return (
    <section className="contract-group" aria-label={`${title} ${contracts.length}개`}>
      <h2 className="contract-group__title">{title} <span className="contract-group__count">{contracts.length}</span></h2>
      <div className="contract-grid">
        {contracts.map((contract) => <ContractCard contract={contract} key={contract.id} />)}
      </div>
    </section>
  );
}

export function DashboardPage() {
  const [contracts, setContracts] = useState<ContractSummaryDto[]>([]);
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

  // 8번 화면에서 체크리스트+계약 직후 행동을 다 완료하면 done으로 이동한다.
  const byStatus = (target: ContractSummaryDto["action_status"]) =>
    contracts.filter((contract) => (contract.action_status ?? "none") === target);
  const notStarted = byStatus("none");
  const inProgress = byStatus("in_progress");
  const done = byStatus("done");

  return (
    <PageShell layout="workspace" step="2 / 8" title="내 계약" description="진행 중인 계약을 다시 열거나 새 계약 확인을 시작하세요.">
      <div className="stack">
        {status === "loading" && <LoadingState title="계약 목록을 불러오는 중" description="저장된 계약 건을 확인하고 있습니다." />}
        {status === "error" && <ErrorState title="계약 목록을 불러오지 못했습니다" description={errorMessage} onRetry={() => void loadContracts()} />}
        {status === "success" && contracts.length === 0 && <EmptyState title="아직 저장된 계약이 없습니다" description="새 계약을 만들어 확인을 시작해 보세요." />}
        {status === "success" && contracts.length > 0 && (
          <div className="contract-groups">
            <ContractGroup title="미행동 계약" contracts={notStarted} />
            <ContractGroup title="행동중 계약" contracts={inProgress} />
            {done.length > 0 && (
              <details className="contract-group contract-group--done">
                <summary>행동 완료 계약 {done.length}개</summary>
                <div className="contract-grid">
                  {done.map((contract) => <ContractCard contract={contract} key={contract.id} />)}
                </div>
              </details>
            )}
          </div>
        )}
        <Link className="button-link" to="/contracts/new">새 계약 만들기</Link>
      </div>
    </PageShell>
  );
}
