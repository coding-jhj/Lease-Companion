import type { ContractStage, ContractSummaryDto, ContractType } from "../../types/api";

// 문서에서 읽을 수 없어 사용자만 답할 수 있는 값. 문서의 못 읽은 항목 확인과 분리해
// 분석 준비 단계에서 받고, 저장은 기존 상황 저장 API를 그대로 쓴다.
export interface SituationAnswer {
  contractType: ContractType | null;
  contractStage: ContractStage;
  depositPaid: boolean;
  signed: boolean;
  moveInDate: string;
  balancePaymentDate: string;
  proxyStatus: "unknown" | "yes" | "no";
}

export const emptySituationAnswer: SituationAnswer = {
  contractType: null,
  contractStage: "계약금 입금 전",
  depositPaid: false,
  signed: false,
  moveInDate: "",
  balancePaymentDate: "",
  proxyStatus: "unknown",
};

export function situationAnswerFromContract(contract: ContractSummaryDto): SituationAnswer {
  return {
    contractType: contract.contract_type,
    contractStage: contract.contract_stage ?? "계약금 입금 전",
    depositPaid: contract.deposit_paid ?? false,
    signed: contract.signed ?? false,
    moveInDate: contract.move_in_date ?? "",
    balancePaymentDate: contract.balance_payment_date ?? "",
    proxyStatus: contract.is_proxy_contract === null
      ? "unknown"
      : contract.is_proxy_contract ? "yes" : "no",
  };
}

const stageOptions: Array<{ value: ContractStage; label: string }> = [
  { value: "계약금 입금 전", label: "아직 돈을 보내지 않았어요" },
  { value: "서명 전", label: "계약서를 받았고 서명 전이에요" },
  { value: "계약 직후", label: "이미 서명했어요" },
];

export function situationAnswered(value: SituationAnswer): boolean {
  return value.contractType !== null;
}

export function SituationAnswers({
  value,
  busy,
  onChange,
}: {
  value: SituationAnswer;
  busy: boolean;
  onChange: (next: SituationAnswer) => void;
}) {
  const update = (patch: Partial<SituationAnswer>) => onChange({ ...value, ...patch });

  return (
    <section className="situation-answers" aria-labelledby="situation-answers-title">
      <header>
        <h3 id="situation-answers-title">계약 상황 알려주기</h3>
        <p>문서에서 읽을 수 없는 내용입니다. 지금 알고 있는 것만 골라 주세요.</p>
      </header>
      <div className="situation-answers__grid">
        <fieldset disabled={busy}>
          <legend className="field-label">계약 유형<small>보증금만 내면 전세, 보증금과 월세를 함께 내면 보증부 월세입니다.</small></legend>
          {(["전세", "보증부 월세", "일반 월세"] as ContractType[]).map((type) => (
            <label className="check-item" key={type}>
              <input
                type="radio"
                name="situation-contract-type"
                value={type}
                checked={value.contractType === type}
                onChange={() => update({ contractType: type })}
              />
              {type}
            </label>
          ))}
        </fieldset>
        <fieldset disabled={busy}>
          <legend className="field-label">지금 어디까지 진행했나요?</legend>
          {stageOptions.map((option) => (
            <label className="check-item" key={option.value}>
              <input
                type="radio"
                name="situation-contract-stage"
                value={option.value}
                checked={value.contractStage === option.value}
                onChange={() => update({ contractStage: option.value })}
              />
              {option.label}
            </label>
          ))}
        </fieldset>
        <fieldset disabled={busy}>
          <legend className="field-label">계약금을 이미 지급했습니다</legend>
          <div className="choice-row">
            <label className="check-item">
              <input type="radio" name="situation-deposit-paid" checked={value.depositPaid} aria-label="계약금을 이미 지급했습니다 예" onChange={() => update({ depositPaid: true })} />예
            </label>
            <label className="check-item">
              <input type="radio" name="situation-deposit-paid" checked={!value.depositPaid} aria-label="계약금을 이미 지급했습니다 아니요" onChange={() => update({ depositPaid: false })} />아니요
            </label>
          </div>
        </fieldset>
        <fieldset disabled={busy}>
          <legend className="field-label">계약서에 이미 서명했습니다</legend>
          <div className="choice-row">
            <label className="check-item">
              <input type="radio" name="situation-signed" checked={value.signed} aria-label="계약서에 이미 서명했습니다 예" onChange={() => update({ signed: true })} />예
            </label>
            <label className="check-item">
              <input type="radio" name="situation-signed" checked={!value.signed} aria-label="계약서에 이미 서명했습니다 아니요" onChange={() => update({ signed: false })} />아니요
            </label>
          </div>
        </fieldset>
        <fieldset disabled={busy}>
          <legend className="field-label">날짜<small>정해진 날짜만 입력해 주세요.</small></legend>
          <label className="check-item">
            <span className="field-label">입주 예정일</span>
            <input type="date" value={value.moveInDate} onChange={(event) => update({ moveInDate: event.target.value })} />
          </label>
          <label className="check-item">
            <span className="field-label">잔금 지급 예정일</span>
            <input type="date" value={value.balancePaymentDate} onChange={(event) => update({ balancePaymentDate: event.target.value })} />
          </label>
        </fieldset>
        <fieldset disabled={busy}>
          <legend className="field-label">계약하는 사람<small>집주인 본인이 아닌 사람이 진행하는 경우를 말합니다.</small></legend>
          <label className="check-item">
            <input type="radio" name="situation-proxy" checked={value.proxyStatus === "yes"} onChange={() => update({ proxyStatus: "yes" })} />집주인 대신 다른 사람이 계약해요
          </label>
          <label className="check-item">
            <input type="radio" name="situation-proxy" checked={value.proxyStatus === "no"} onChange={() => update({ proxyStatus: "no" })} />집주인이 직접 계약해요
          </label>
          <label className="check-item">
            <input type="radio" name="situation-proxy" checked={value.proxyStatus === "unknown"} onChange={() => update({ proxyStatus: "unknown" })} />잘 모르겠어요
          </label>
        </fieldset>
        {value.proxyStatus === "yes" && (
          <div className="beginner-guide situation-answers__guide">
            <strong>계약 전에 확인해 주세요.</strong>
            <ul><li>위임장</li><li>인감증명서</li></ul>
          </div>
        )}
      </div>
    </section>
  );
}
