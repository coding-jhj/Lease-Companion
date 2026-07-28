import type { DamagePatternComparisonDto, DamagePatternStatus } from "../../types/api";
import { EvidenceDisclosure } from "../evidence-sources/EvidenceDisclosure";
import { plainGuideById, plainJudgmentGuides } from "../judgment-results/plainGuides";
import { RecentPressReleaseLookup } from "./RecentPressReleaseLookup";

// DP는 연결된 판정(J)·규칙(R)의 쉬운 설명을 재사용한다. 판정을 우선하고, 없으면 규칙으로
// 폴백한다. 큐레이션된 가이드가 있는 첫 id를 골라 일반 안내 폴백을 최소화한다.
function guideForPattern(item: DamagePatternComparisonDto) {
  const linkedId = [...item.related_judgment_ids, ...item.related_rule_ids].find(
    (id) => id in plainJudgmentGuides,
  );
  return plainGuideById(linkedId);
}

const statusClass: Record<DamagePatternStatus, string> = {
  "관련 확인 신호 있음": "signal",
  "제출 자료에서 관련 신호 미확인": "clear",
  "자료 부족으로 확인 불가": "unknown",
  "예방 확인 필요": "preventive",
};

function PatternRow({ item }: { item: DamagePatternComparisonDto }) {
  const guide = guideForPattern(item);
  return (
    <div className="damage-patterns__row" role="row">
      <strong role="cell">{item.pattern_name}</strong>
      <span role="cell" className={`damage-patterns__status damage-patterns__status--${statusClass[item.status]}`}>{item.status}</span>
      <div role="cell">
        <p>{item.reason}</p>
        <details><summary>근거와 실제 사례</summary>
          <EvidenceDisclosure
            sources={item.official_sources}
            limitations={item.limitations}
            explanation={guide.explanation}
            financialImpact={guide.financialImpact}
            idPrefix={`damage-pattern-${item.pattern_id}`}
            hideLimitations
          />
          <RecentPressReleaseLookup
            idPrefix={`damage-pattern-${item.pattern_id}`}
            patternId={item.pattern_id}
            patternName={item.pattern_name}
          />
        </details>
      </div>
    </div>
  );
}

export function DamagePatternTable({ items }: { items: DamagePatternComparisonDto[] }) {
  if (items.length === 0) return null;
  const actionable = items.filter((item) => (
    item.status === "관련 확인 신호 있음" || item.status === "예방 확인 필요"
  ));
  const unknown = items.filter((item) => item.status === "자료 부족으로 확인 불가");
  const noSignal = items.filter(
    (item) => item.status === "제출 자료에서 관련 신호 미확인",
  );

  function PatternGroup({
    title,
    groupItems,
    label,
  }: {
    title: string;
    groupItems: DamagePatternComparisonDto[];
    label: string;
  }) {
    if (groupItems.length === 0) return null;
    return (
      <section className="damage-patterns__group" aria-labelledby={`${label}-title`}>
        <h3 id={`${label}-title`}>{title}</h3>
        <div className="damage-patterns__table" role="table" aria-label={title}>
          <div className="damage-patterns__row damage-patterns__head" role="row">
            <span role="columnheader">피해 유형</span>
            <span role="columnheader">분석 결과</span>
            <span role="columnheader">판단 근거</span>
          </div>
          {groupItems.map((item) => <PatternRow item={item} key={item.pattern_id} />)}
        </div>
      </section>
    );
  }

  return (
    <section className="damage-patterns" aria-labelledby="damage-pattern-title">
      <div className="section-heading">
        <h2 id="damage-pattern-title">주요 금전피해 유형 비교</h2>
        <p>현재 제출된 계약서와 등기사항증명서 범위에서 비교합니다</p>
      </div>
      <PatternGroup
        title="현재 자료에서 먼저 확인할 금전 피해 유형"
        groupItems={actionable}
        label="damage-actionable"
      />
      <PatternGroup
        title="자료 부족으로 확인 불가"
        groupItems={unknown}
        label="damage-unknown"
      />
      <PatternGroup
        title="제출 자료에서 관련 신호 미확인"
        groupItems={noSignal}
        label="damage-no-signal"
      />
    </section>
  );
}
