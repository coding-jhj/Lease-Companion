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
    <PageShell step="3 / 8" title="지금 계약 상황 알려주기" description="정확히 모르는 내용은 비워두거나 ‘잘 모르겠어요’를 선택해도 됩니다.">
      <form className="stack" onSubmit={submit}>
        <div className="beginner-guide"><strong>모두 알고 있어야 하는 것은 아니에요.</strong><p>현재 알고 있는 내용만 입력하면, 확인하지 못한 부분은 결과에서 따로 알려드립니다.</p></div>
        <label><span className="field-label">계약 유형<small>보증금만 내면 전세, 보증금과 월세를 함께 내면 보증부 월세입니다.</small></span><select value={contractType} onChange={(event) => setContractType(event.target.value as ContractType)}><option>전세</option><option>보증부 월세</option><option>일반 월세</option></select></label>
        <label><span className="field-label">현재 어디까지 진행했나요?<small>가장 가까운 단계를 선택하세요.</small></span><select value={contractStage} onChange={(event) => setContractStage(event.target.value as ContractStage)}><option>계약금 입금 전</option><option>서명 전</option><option>계약 직후</option></select></label>
        <label className="check-item"><input type="checkbox" checked={depositPaid} onChange={(event) => setDepositPaid(event.target.checked)} />계약금을 이미 지급했습니다</label>
        <label className="check-item"><input type="checkbox" checked={signed} onChange={(event) => setSigned(event.target.checked)} />계약서에 이미 서명했습니다</label>
        <label><span className="field-label">입주 예정일<small>정해지지 않았다면 비워두세요.</small></span><input type="date" value={moveInDate} onChange={(event) => setMoveInDate(event.target.value)} /></label>
        <label><span className="field-label">잔금 지급 예정일<small>나머지 보증금을 보내기로 한 날입니다. 모르면 비워두세요.</small></span><input type="date" value={balancePaymentDate} onChange={(event) => setBalancePaymentDate(event.target.value)} /></label>
        <label><span className="field-label">집주인이 아닌 사람이 대신 계약하나요?<small>가족·직원·그 밖의 대리인이 진행하는 경우를 말합니다.</small></span><select value={proxyStatus} onChange={(event) => setProxyStatus(event.target.value as "unknown" | "yes" | "no")}><option value="unknown">잘 모르겠어요</option><option value="yes">예</option><option value="no">아니요</option></select></label>
        <button type="submit">다음: 준비한 문서 확인</button>
      </form>
    </PageShell>
  );
}
