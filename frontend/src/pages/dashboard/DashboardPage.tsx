import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ErrorState, LoadingState } from "../../components/feedback/AsyncState";
import { PageShell } from "../../components/layout/PageShell";
import { mvpService } from "../../services/mvpService";
import type { ContractSummaryDto } from "../../types/api";

function primaryActionFor(contract: ContractSummaryDto) {
  switch (contract.action_status ?? "none") {
    case "in_progress":
      return { label: "이어서 확인하기", to: `/contracts/${contract.id}` };
    case "done":
      return { label: "확인 결과 보기", to: `/contracts/${contract.id}/report` };
    default:
      return { label: "점검 시작하기", to: `/contracts/${contract.id}/upload` };
  }
}

function ContractCard({ contract, onDeleted }: { contract: ContractSummaryDto; onDeleted: () => void }) {
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState("");
  const primaryAction = primaryActionFor(contract);

  // 7번(계약 상세)의 삭제와 동일한 확인·서비스 호출. 목록 화면이므로 성공 시 목록을 재조회한다.
  async function deleteContract() {
    if (!window.confirm("이 계약과 저장된 분석 이력을 삭제할까요? 삭제한 데이터는 복구할 수 없습니다.")) return;
    setDeleting(true);
    setDeleteError("");
    try {
      await mvpService.deleteContract(contract.id);
      onDeleted();
    } catch {
      setDeleteError("계약을 삭제하지 못했습니다. 저장된 계약 정보는 그대로 있습니다. 다시 시도해 주세요.");
      setDeleting(false);
    }
  }

  return (
    <article className="contract-card">
      <strong>{contract.title}</strong>
      <span>{contract.contract_stage ?? "상황 입력 전"} · {new Date(contract.created_at).toLocaleDateString("ko-KR")}</span>
      <div className="card-actions">
        <Link className="button-link" to={primaryAction.to}>{primaryAction.label}</Link>
        <details className="contract-card__management">
          <summary>계약 관리</summary>
          <div className="contract-card__management-actions">
            <Link className="text-link" to={"/contracts/" + contract.id}>계약 상세 보기</Link>
            {(contract.action_status ?? "none") === "done" && <Link className="text-link text-link--report" to={"/contracts/" + contract.id + "/report"}>확인 결과 다시 보기</Link>}
            <button className="text-link text-link--danger" type="button" disabled={deleting} onClick={() => void deleteContract()}>
              {deleting ? "삭제 중" : "계약 삭제"}
            </button>
          </div>
        </details>
      </div>
      {deleteError && <p className="error" role="alert">{deleteError}</p>}
    </article>
  );
}

function ContractGroup({ title, contracts, onDeleted }: { title: string; contracts: ContractSummaryDto[]; onDeleted: () => void }) {
  if (contracts.length === 0) return null;
  return (
    <section className="contract-group" aria-label={`${title} ${contracts.length}개`}>
      <h2 className="contract-group__title">{title} <span className="contract-group__count">{contracts.length}</span></h2>
      <div className="contract-grid">
        {contracts.map((contract) => <ContractCard contract={contract} onDeleted={onDeleted} key={contract.id} />)}
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
    } catch {
      setErrorMessage("계약 목록을 불러오지 못했습니다. 저장된 계약 정보는 변경되지 않았습니다. 다시 시도해 주세요.");
      setStatus("error");
    }
  }

  useEffect(() => { void loadContracts(); }, []);

  // 7번 화면에서 체크리스트+계약 직후 행동을 다 완료하면 done으로 이동한다.
  const byStatus = (target: ContractSummaryDto["action_status"]) =>
    contracts.filter((contract) => (contract.action_status ?? "none") === target);
  const notStarted = byStatus("none");
  const inProgress = byStatus("in_progress");
  const done = byStatus("done");

  return (
    <PageShell layout="workspace" step="2 / 7" title="내 계약" description="진행 중인 계약을 다시 열거나 새 계약 확인을 시작하세요.">
      <div className="stack">
        {status === "loading" && <LoadingState title="계약 목록을 불러오는 중" description="저장된 계약 건을 확인하고 있습니다." />}
        {status === "error" && <ErrorState title="계약 목록을 불러오지 못했습니다" description={errorMessage} onRetry={() => void loadContracts()} />}
        {status === "success" && contracts.length === 0 && (
          <section className="dashboard-empty" aria-labelledby="dashboard-empty-title">
            <div className="dashboard-empty__intro">
              <p>처음이어도 괜찮습니다</p>
              <h2 id="dashboard-empty-title">첫 계약 점검을 시작해 보세요</h2>
              <span>계약서 초안을 올리면 읽은 내용을 확인한 뒤, 물어볼 말과 다음 행동을 정리해 드립니다.</span>
            </div>
            <ol className="dashboard-empty__steps" aria-label="계약 점검 과정">
              <li><strong>1</strong><span><b>계약서 올리기</b><small>PDF 또는 사진을 준비합니다.</small></span></li>
              <li><strong>2</strong><span><b>읽은 내용 확인</b><small>잘못 읽은 내용은 직접 고칩니다.</small></span></li>
              <li><strong>3</strong><span><b>확인 결과 보기</b><small>물어볼 말과 할 일을 확인합니다.</small></span></li>
            </ol>
            <div className="dashboard-empty__actions">
              <Link className="button-link" to="/contracts/new">계약서 올리고 점검하기</Link>
              <Link className="button-link secondary" to="/prepare">아직 계약서가 없어요</Link>
            </div>
            <Link className="dashboard-practice-link" to="/practice">계약 상황을 먼저 연습하기</Link>
          </section>
        )}
        {status === "success" && contracts.length > 0 && (
          <>
            <section className="dashboard-start-actions" aria-label="새로운 계약 확인">
              <div>
                <h2>새로운 계약을 확인할까요?</h2>
                <p>계약서가 있다면 바로 점검하고, 없다면 준비할 내용을 먼저 확인할 수 있습니다.</p>
              </div>
              <div>
                <Link className="button-link" to="/contracts/new">새 계약 점검</Link>
                <Link className="button-link secondary" to="/practice">계약 연습</Link>
              </div>
            </section>
            <div className="contract-groups">
              <ContractGroup title="점검을 시작하지 않은 계약" contracts={notStarted} onDeleted={loadContracts} />
              <ContractGroup title="확인 중인 계약" contracts={inProgress} onDeleted={loadContracts} />
              {done.length > 0 && (
                <details className="contract-group contract-group--done">
                  <summary>확인을 마친 계약 {done.length}개</summary>
                  <div className="contract-grid">
                    {done.map((contract) => <ContractCard contract={contract} onDeleted={loadContracts} key={contract.id} />)}
                  </div>
                </details>
              )}
            </div>
          </>
        )}
      </div>
    </PageShell>
  );
}
