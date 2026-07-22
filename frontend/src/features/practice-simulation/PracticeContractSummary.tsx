import type { PracticeContractSummary as ContractSummary } from "../../types/practice";

export function PracticeContractSummary({ contract, compact = false }: { contract: ContractSummary; compact?: boolean }) {
  const rows = [
    ["계약 유형", contract.contractType],
    ["주택 유형", contract.housingType],
    ["임대차보증금", contract.deposit],
    ["계약금", contract.contractPayment],
    ["잔금", contract.balancePayment],
    ["계약기간", contract.contractPeriod],
    ["임대인", contract.landlord],
    ["임차인", contract.tenant],
    ["입주 예정일", contract.moveInDate],
  ];

  return (
    <section className={`practice-contract${compact ? " practice-contract--compact" : ""}`} aria-label="모의 계약서 요약">
      <header>
        <span>합성 문서</span>
        <h2>주택임대차계약서</h2>
      </header>
      {!compact && (
        <dl className="practice-contract__facts">
          {rows.map(([label, value]) => (
            <div key={label}><dt>{label}</dt><dd>{value}</dd></div>
          ))}
        </dl>
      )}
      <div className="practice-contract__clauses">
        <h3>특약사항</h3>
        <ol>
          {contract.specialClauses.map((clause) => <li key={clause}>{clause}</li>)}
        </ol>
      </div>
    </section>
  );
}
