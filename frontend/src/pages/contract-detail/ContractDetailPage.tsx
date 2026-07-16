import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { EmptyState, ErrorState, LoadingState } from "../../components/feedback/AsyncState";
import { PageShell } from "../../components/layout/PageShell";
import { mvpService } from "../../services/mvpService";
import type { ChecklistItem } from "../../types/api";

export function ContractDetailPage() {
  const { contractId = "contract-demo-001" } = useParams();
  const [items, setItems] = useState<ChecklistItem[]>([]);
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [errorMessage, setErrorMessage] = useState("");

  async function loadChecklist() {
    setStatus("loading");
    try {
      setItems(await mvpService.getChecklist(contractId));
      setStatus("success");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "체크리스트를 불러오지 못했습니다.");
      setStatus("error");
    }
  }

  useEffect(() => { void loadChecklist(); }, [contractId]);

  function toggle(id: string) {
    setItems((current) => current.map((item) => item.id === id ? { ...item, completed: !item.completed } : item));
  }

  return (
    <PageShell step="8 / 8" title="체크리스트와 계약 직후 행동" description="확인한 항목을 계약 건에 저장하고 다시 열어볼 수 있습니다.">
      <div className="stack">
        {status === "loading" && <LoadingState title="체크리스트를 불러오는 중" description="저장된 확인 상태를 준비하고 있습니다." />}
        {status === "error" && <ErrorState title="체크리스트를 불러오지 못했습니다" description={errorMessage} onRetry={() => void loadChecklist()} />}
        {status === "success" && items.length === 0 && <EmptyState title="아직 체크리스트 항목이 없습니다" description="리포트가 생성되면 확인 행동이 여기에 표시됩니다." />}
        {status === "success" && items.map((item) => <label className="check-item" key={item.id}><input type="checkbox" checked={item.completed} onChange={() => toggle(item.id)} />{item.label}</label>)}
        <Link className="button-link secondary" to={`/contracts/${contractId}/report`}>리포트 다시 보기</Link>
        <Link className="button-link" to="/contracts">대시보드로 돌아가기</Link>
      </div>
    </PageShell>
  );
}
