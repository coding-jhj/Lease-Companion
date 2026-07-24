import { useRef, useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { PageShell } from "../../components/layout/PageShell";
import { mvpService } from "../../services/mvpService";
import type { ContractStage, ContractType } from "../../types/api";
import { contractIdFromRoute } from "../../utils/contractId";

const stageOptions: Array<{ value: ContractStage; label: string }> = [
  { value: "계약금 입금 전", label: "아직 돈을 보내지 않았어요" },
  { value: "서명 전", label: "계약서를 받았고 서명 전이에요" },
  { value: "계약 직후", label: "이미 서명했어요" },
];

export function ContractSituationPage() {
  const { contractId: routeContractId } = useParams();
  const contractId = contractIdFromRoute(routeContractId);
  const navigate = useNavigate();
  const [contractType, setContractType] = useState<ContractType | null>(null);
  const [contractStage, setContractStage] = useState<ContractStage>("계약금 입금 전");
  const [depositPaid, setDepositPaid] = useState(false);
  const [signed, setSigned] = useState(false);
  const [showDateInputs, setShowDateInputs] = useState(false);
  const [moveInDate, setMoveInDate] = useState("");
  const [balancePaymentDate, setBalancePaymentDate] = useState("");
  const [proxyStatus, setProxyStatus] = useState<"unknown" | "yes" | "no">("unknown");
  const [error, setError] = useState<string | null>(null);
  const firstContractTypeInput = useRef<HTMLInputElement>(null);

  function clearDates() {
    setMoveInDate("");
    setBalancePaymentDate("");
    setShowDateInputs(false);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);

    if (!contractType) {
      setError("계약 유형을 선택해 주세요.");
      firstContractTypeInput.current?.focus();
      return;
    }

    try {
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
    } catch {
      setError("저장하지 못했습니다. 다시 시도해 주세요.");
    }
  }

  return (
    <PageShell layout="workspace" step="3 / 8" title="지금 계약 상황 알려주기" description="현재 알고 있는 내용만 골라 주세요. 모르는 내용은 나중에 확인해도 됩니다.">
      <form className="stack" onSubmit={submit}>
        <div className="situation-columns">
        <section className="stack" aria-labelledby="contract-type-question">
          <h2 id="contract-type-question">어떤 계약을 준비하고 있나요?</h2>
          <fieldset>
            <legend className="field-label">계약 유형<small>보증금만 내면 전세, 보증금과 월세를 함께 내면 보증부 월세입니다.</small></legend>
            {(["전세", "보증부 월세", "일반 월세"] as ContractType[]).map((type) => (
              <label key={type} className="check-item"><input ref={type === "전세" ? firstContractTypeInput : undefined} type="radio" name="contract-type" value={type} checked={contractType === type} onChange={() => setContractType(type)} />{type}</label>
            ))}
          </fieldset>
        </section>

        <section className="stack" aria-labelledby="contract-stage-question">
          <h2 id="contract-stage-question">지금 어디까지 진행했나요?</h2>
          <fieldset>
            <legend className="field-label">가장 가까운 단계를 골라 주세요.</legend>
            {stageOptions.map((option) => (
              <label key={option.value} className="check-item"><input type="radio" name="contract-stage" value={option.value} checked={contractStage === option.value} onChange={() => setContractStage(option.value)} />{option.label}</label>
            ))}
          </fieldset>
          <fieldset>
            <legend className="field-label">계약금을 이미 지급했습니다</legend>
            <div className="choice-row">
              <label className="check-item"><input type="radio" name="deposit-paid" checked={depositPaid} onChange={() => setDepositPaid(true)} aria-label="계약금을 이미 지급했습니다 예" />예</label>
              <label className="check-item"><input type="radio" name="deposit-paid" checked={!depositPaid} onChange={() => setDepositPaid(false)} aria-label="계약금을 이미 지급했습니다 아니요" />아니요</label>
            </div>
          </fieldset>
          <fieldset>
            <legend className="field-label">계약서에 이미 서명했습니다</legend>
            <div className="choice-row">
              <label className="check-item"><input type="radio" name="signed" checked={signed} onChange={() => setSigned(true)} aria-label="계약서에 이미 서명했습니다 예" />예</label>
              <label className="check-item"><input type="radio" name="signed" checked={!signed} onChange={() => setSigned(false)} aria-label="계약서에 이미 서명했습니다 아니요" />아니요</label>
            </div>
          </fieldset>
        </section>

        <section className="stack" aria-labelledby="additional-question">
          <h2 id="additional-question">추가로 확인할 내용</h2>
          {showDateInputs ? (
            <fieldset>
              <legend className="field-label">날짜<small>정해진 날짜만 입력해 주세요.</small></legend>
              <label><span className="field-label">입주 예정일</span><input type="date" value={moveInDate} onChange={(event) => setMoveInDate(event.target.value)} /></label>
              <label><span className="field-label">잔금 지급 예정일</span><input type="date" value={balancePaymentDate} onChange={(event) => setBalancePaymentDate(event.target.value)} /></label>
              <button className="secondary" type="button" onClick={clearDates}>아직 몰라요</button>
            </fieldset>
          ) : (
            <button className="secondary situation-date-toggle" type="button" onClick={() => setShowDateInputs(true)}>날짜를 입력할게요</button>
          )}
          <fieldset>
            <legend className="field-label">계약하는 사람<small>집주인 본인이 아닌 사람이 진행하는 경우를 말합니다.</small></legend>
            <label className="check-item"><input type="radio" name="proxy-status" checked={proxyStatus === "yes"} onChange={() => setProxyStatus("yes")} />집주인 대신 다른 사람이 계약해요</label>
            <label className="check-item"><input type="radio" name="proxy-status" checked={proxyStatus === "no"} onChange={() => setProxyStatus("no")} />집주인이 직접 계약해요</label>
            <label className="check-item"><input type="radio" name="proxy-status" checked={proxyStatus === "unknown"} onChange={() => setProxyStatus("unknown")} />잘 모르겠어요</label>
          </fieldset>
          {proxyStatus === "yes" && <div className="beginner-guide"><strong>계약 전에 확인해 주세요.</strong><ul><li>위임장</li><li>인감증명서</li></ul></div>}
        </section>
        </div>

        {error && <p role="alert">{error}</p>}
        <button className="primary" type="submit">다음: 문서 준비하기</button>
      </form>
    </PageShell>
  );
}
