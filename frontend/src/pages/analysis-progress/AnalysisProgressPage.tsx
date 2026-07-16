import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { PageShell } from "../../components/layout/PageShell";
import { mvpService } from "../../services/mvpService";

export function AnalysisProgressPage() {
  const { contractId = "contract-demo-001" } = useParams();
  const navigate = useNavigate();
  const [complete, setComplete] = useState(false);
  useEffect(() => { void mvpService.startAnalysis(contractId).then(() => setComplete(true)); }, [contractId]);

  return (
    <PageShell step="분석 중" title={complete ? "분석 준비 완료" : "계약 내용을 확인하고 있어요"} description="규칙 판정과 공식 근거를 정리합니다. 종합 안전 점수는 제공하지 않습니다.">
      <button type="button" disabled={!complete} onClick={() => navigate(`/contracts/${contractId}/report`)}>{complete ? "리포트 보기" : "분석 중…"}</button>
    </PageShell>
  );
}
