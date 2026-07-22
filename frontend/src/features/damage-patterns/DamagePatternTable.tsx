import type { DamagePatternComparisonDto, DamagePatternStatus } from "../../types/api";
import { EvidenceDisclosure } from "../evidence-sources/EvidenceDisclosure";

const statusClass: Record<DamagePatternStatus, string> = {
  "관련 확인 신호 있음": "signal",
  "제출 자료에서 관련 신호 미확인": "clear",
  "자료 부족으로 확인 불가": "unknown",
  "예방 확인 필요": "preventive",
};

export function DamagePatternTable({ items }: { items: DamagePatternComparisonDto[] }) {
  if (items.length === 0) return null;
  return (
    <section className="damage-patterns" aria-labelledby="damage-pattern-title">
      <div className="section-heading">
        <p>현재 제출된 계약서와 등기사항증명서 범위에서 비교합니다</p>
        <h2 id="damage-pattern-title">주요 금전피해 유형 비교</h2>
      </div>
      <div className="damage-patterns__table" role="table" aria-label="주요 금전피해 유형 비교">
        <div className="damage-patterns__row damage-patterns__head" role="row">
          <span role="columnheader">피해 유형</span><span role="columnheader">분석 결과</span><span role="columnheader">판단 근거</span>
        </div>
        {items.map((item) => (
          <div className="damage-patterns__row" role="row" key={item.pattern_id}>
            <strong role="cell">{item.pattern_name}</strong>
            <span role="cell" className={`damage-patterns__status damage-patterns__status--${statusClass[item.status]}`}>{item.status}</span>
            <div role="cell">
              <p>{item.reason}</p>
              <details><summary>근거와 분석 한계</summary>
                <EvidenceDisclosure
                  sources={item.official_sources}
                  limitations={item.limitations}
                  explanation="이 비교는 기존 규칙 판정을 피해 유형 관점으로 다시 묶어 보여줍니다."
                  financialImpact="관련 신호가 없더라도 향후 권리변동이나 제출되지 않은 자료까지 확인한 것은 아닙니다."
                  idPrefix={`damage-pattern-${item.pattern_id}`}
                />
                {item.reference_cases.length > 0
                  ? (
                    <section aria-label={`${item.pattern_name} 검증된 유사 참고 사례`}>
                      <h3>검증된 유사 참고 사례</h3>
                      <ul className="reference-case-list">
                        {item.reference_cases.map((reference) => (
                          <li key={reference.reference_case_id}>
                            <a href={reference.source_url} target="_blank" rel="noreferrer">{reference.title}</a>
                            <p>{reference.summary}</p>
                            <small>{reference.publisher} · {reference.verification_scope}</small>
                          </li>
                        ))}
                      </ul>
                    </section>
                  )
                  : <p className="empty-note">현재 비교 상태에 연결된 검증 사례가 없습니다.</p>}
              </details>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
