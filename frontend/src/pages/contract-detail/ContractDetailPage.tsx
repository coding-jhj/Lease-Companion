import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { PageShell } from "../../components/layout/PageShell";
import { mvpService } from "../../services/mvpService";
import type { ChecklistItem } from "../../types/api";

export function ContractDetailPage() {
  const { contractId = "contract-demo-001" } = useParams();
  const [items, setItems] = useState<ChecklistItem[]>([]);
  useEffect(() => { void mvpService.getChecklist(contractId).then(setItems); }, [contractId]);

  function toggle(id: string) {
    setItems((current) => current.map((item) => item.id === id ? { ...item, completed: !item.completed } : item));
  }

  return (
    <PageShell step="8 / 8" title="체크리스트와 계약 직후 행동" description="확인한 항목을 계약 건에 저장하고 다시 열어볼 수 있습니다.">
      <div className="stack">
        {items.map((item) => <label className="check-item" key={item.id}><input type="checkbox" checked={item.completed} onChange={() => toggle(item.id)} />{item.label}</label>)}
        <Link className="button-link secondary" to={`/contracts/${contractId}/report`}>리포트 다시 보기</Link>
        <Link className="button-link" to="/contracts">대시보드로 돌아가기</Link>
      </div>
    </PageShell>
  );
}
