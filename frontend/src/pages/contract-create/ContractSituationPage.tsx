import { useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { PageShell } from "../../components/layout/PageShell";
import { mvpService } from "../../services/mvpService";

export function ContractSituationPage() {
  const { contractId = "contract-demo-001" } = useParams();
  const navigate = useNavigate();
  const [contractType, setContractType] = useState("전세");

  async function submit(event: FormEvent) {
    event.preventDefault();
    await mvpService.saveSituation(contractId, contractType);
    navigate(`/contracts/${contractId}/upload`);
  }

  return (
    <PageShell step="4 / 8" title="계약 상황 입력" description="현재 준비 중인 임대차 계약 유형을 알려주세요.">
      <form className="stack" onSubmit={submit}>
        <label>계약 유형<select value={contractType} onChange={(e) => setContractType(e.target.value)}><option>전세</option><option>보증부 월세</option><option>일반 월세</option></select></label>
        <button type="submit">문서 업로드하기</button>
      </form>
    </PageShell>
  );
}
