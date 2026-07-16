import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { PageShell } from "../../components/layout/PageShell";
import { mvpService } from "../../services/mvpService";
import type { ReportItem } from "../../types/api";

export function ResultReportPage() {
  const { contractId = "contract-demo-001" } = useParams();
  const navigate = useNavigate();
  const [items, setItems] = useState<ReportItem[]>([]);
  useEffect(() => { void mvpService.getReport(contractId).then(setItems); }, [contractId]);

  return (
    <PageShell step="7 / 8" title="계약 확인 리포트" description="항목별 확인 필요성과 다음 질문을 살펴보세요.">
      <div className="stack">
        {items.map((item) => <article className="result-card" key={item.judgmentId}><span className="priority">● {item.priority}</span><h2>{item.title}</h2><p>{item.status} · {item.urgency}</p><p>{item.explanation}</p></article>)}
        <button type="button" onClick={() => navigate(`/contracts/${contractId}`)}>체크리스트로 이동</button>
      </div>
    </PageShell>
  );
}
