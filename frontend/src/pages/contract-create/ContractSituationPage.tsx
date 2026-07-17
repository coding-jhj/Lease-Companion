import { useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { PageShell } from "../../components/layout/PageShell";
import { mvpService } from "../../services/mvpService";
import type { ContractStage, ContractType } from "../../types/api";
import { contractIdFromRoute } from "../../utils/contractId";

export function ContractSituationPage() {
  const { contractId: routeContractId } = useParams();
  const contractId = contractIdFromRoute(routeContractId);
  const navigate = useNavigate();
  const [contractType, setContractType] = useState<ContractType>("전세");
  const [contractStage, setContractStage] = useState<ContractStage>("계약금 입금 전");
  const [depositPaid, setDepositPaid] = useState(false);
  const [signed, setSigned] = useState(false);
  const [moveInDate, setMoveInDate] = useState("");
  const [balancePaymentDate, setBalancePaymentDate] = useState("");
  const [proxyStatus, setProxyStatus] = useState<"unknown" | "yes" | "no">("unknown");

  async function submit(event: FormEvent) {
    event.preventDefault();
    await mvpService.saveSituation(contractId, {
      contract_type: contractType,
      contract_stage: contractStage,
      deposit_paid: depositPaid,
      signed,
      move_in_date: moveInDate || null,
      balance_payment_date: balancePaymentDate || null,
      is_proxy_contract: proxyStatus === "unknown" ? null : proxyStatus === "yes",
    });
    navigate(`/contracts/${contractId}/upload`);
  }

  return (
    <PageShell step="3 / 8" title="계약 상황 입력" description="현재 계약 단계와 지급·서명·일정 정보를 입력하세요.">
      <form className="stack" onSubmit={submit}>
        <label>계약 유형<select value={contractType} onChange={(event) => setContractType(event.target.value as ContractType)}><option>전세</option><option>보증부 월세</option><option>일반 월세</option></select></label>
        <label>계약 단계<select value={contractStage} onChange={(event) => setContractStage(event.target.value as ContractStage)}><option>계약금 입금 전</option><option>서명 전</option><option>계약 직후</option></select></label>
        <label className="check-item"><input type="checkbox" checked={depositPaid} onChange={(event) => setDepositPaid(event.target.checked)} />계약금을 이미 지급했습니다</label>
        <label className="check-item"><input type="checkbox" checked={signed} onChange={(event) => setSigned(event.target.checked)} />계약서에 이미 서명했습니다</label>
        <label>입주일<input type="date" value={moveInDate} onChange={(event) => setMoveInDate(event.target.value)} /></label>
        <label>잔금 지급일<input type="date" value={balancePaymentDate} onChange={(event) => setBalancePaymentDate(event.target.value)} /></label>
        <label>대리 계약 여부<select value={proxyStatus} onChange={(event) => setProxyStatus(event.target.value as "unknown" | "yes" | "no")}><option value="unknown">모름</option><option value="yes">예</option><option value="no">아니요</option></select></label>
        <button type="submit">문서 업로드하기</button>
      </form>
    </PageShell>
  );
}
