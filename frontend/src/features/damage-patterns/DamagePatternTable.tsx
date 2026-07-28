import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import type { DamagePatternComparisonDto, DamagePatternStatus } from "../../types/api";
import { EvidenceDisclosure } from "../evidence-sources/EvidenceDisclosure";
import { plainGuideById, plainJudgmentGuides } from "../judgment-results/plainGuides";

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

const patternGuideById: Record<string, { checkText: string; additionalCheck: string }> = {
  DP01: {
    checkText: "계약 상대의 이름과 등기사항증명서에 적힌 소유자 이름을 비교하세요.",
    additionalCheck: "대리 계약이라면 위임장·인감증명서 등 계약 권한을 증명하는 서류도 확인하세요.",
  },
  DP02: {
    checkText: "입금 계좌의 예금주가 임대인 또는 적법한 계약 상대와 같은지 확인하세요.",
    additionalCheck: "다른 명의의 계좌라면 계좌 관계와 입금 요청 근거를 서면으로 확인하세요.",
  },
  DP03: {
    checkText: "공식 실거래 자료로 확인한 주택 시세와 보증금의 비율을 비교하세요.",
    additionalCheck: "시세가 불분명하거나 보증금 비율이 높다면 반환보증 가입 가능 여부도 확인하세요.",
  },
  DP04: {
    checkText: "최신 등기사항증명서에서 근저당권·압류와 선순위 권리관계를 확인하세요.",
    additionalCheck: "채권최고액과 실제 채무액, 말소하기로 한 권리가 있다면 이행 시점도 확인하세요.",
  },
  DP05: {
    checkText: "신탁원부에서 임대차계약을 체결하고 보증금을 받을 권한이 누구에게 있는지 확인하세요.",
    additionalCheck: "신탁회사 동의가 필요한 계약이라면 동의서와 보증금 반환 주체도 확인하세요.",
  },
  DP06: {
    checkText: "다가구주택 등이라면 나보다 먼저 입주한 임차인의 보증금 규모를 확인하세요.",
    additionalCheck: "선순위 임차보증금과 담보 금액은 임대인에게 서면 자료로 요청하세요.",
  },
  DP07: {
    checkText: "계약일부터 잔금 지급 다음 날까지 추가 담보권을 설정하지 않는 특약을 확인하세요.",
    additionalCheck: "잔금일에는 최신 등기사항증명서를 다시 확인하고 특약 이행 여부를 기록으로 남기세요.",
  },
  DP08: {
    checkText: "신규 임차인의 입주 여부와 관계없이 계약 종료일에 보증금을 반환하는지 확인하세요.",
    additionalCheck: "반환 시점이 다른 조건과 연결돼 있다면 문구 수정을 요청한 뒤 서명하세요.",
  },
};

function PatternRow({ item }: { item: DamagePatternComparisonDto }) {
  const guide = guideForPattern(item);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const modalTitleId = `damage-pattern-${item.pattern_id}-modal-title`;

  useEffect(() => {
    if (!isModalOpen) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeRef.current?.focus();
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setIsModalOpen(false);
    };
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", closeOnEscape);
      triggerRef.current?.focus();
    };
  }, [isModalOpen]);

  return (
    <div className="damage-patterns__row" role="row">
      <strong role="cell">{item.pattern_name}</strong>
      <span role="cell" className={`damage-patterns__status damage-patterns__status--${statusClass[item.status]}`}>{item.status}</span>
      <div role="cell">
        <p>{item.reason}</p>
        <button
          ref={triggerRef}
          type="button"
          className="damage-patterns__evidence-button"
          onClick={() => setIsModalOpen(true)}
          aria-haspopup="dialog"
        >
          <span aria-hidden="true">▸</span> 근거와 실제 사례
        </button>
        {isModalOpen && createPortal(
          <div
            className="damage-pattern-modal__backdrop"
            onMouseDown={(event) => {
              if (event.target === event.currentTarget) setIsModalOpen(false);
            }}
          >
            <section
              className="damage-pattern-modal"
              role="dialog"
              aria-modal="true"
              aria-labelledby={modalTitleId}
            >
              <header className="damage-pattern-modal__header">
                <div>
                  <span className="damage-pattern-modal__eyebrow">계약 전 확인할 피해 유형</span>
                  <h2 id={modalTitleId}>{item.pattern_name}</h2>
                </div>
                <button
                  ref={closeRef}
                  type="button"
                  className="damage-pattern-modal__close"
                  onClick={() => setIsModalOpen(false)}
                  aria-label="창 닫기"
                >
                  <span className="damage-pattern-modal__close-icon" aria-hidden="true" />
                </button>
              </header>
              <div className="damage-pattern-modal__body">
                <EvidenceDisclosure
                  sources={item.official_sources}
                  limitations={item.limitations}
                  explanation={guide.explanation}
                  financialImpact={guide.financialImpact}
                  idPrefix={`damage-pattern-${item.pattern_id}`}
                  hideLimitations
                  sourceLabel="관련 공식자료"
                  damagePatternGuide={patternGuideById[item.pattern_id]}
                />
              </div>
            </section>
          </div>,
          document.body,
        )}
      </div>
    </div>
  );
}

function PatternGroup({
  title,
  groupItems,
  label,
  initiallyOpen = false,
}: {
  title: string;
  groupItems: DamagePatternComparisonDto[];
  label: string;
  initiallyOpen?: boolean;
}) {
  const [expanded, setExpanded] = useState(initiallyOpen);
  const headingId = `${label}-title`;
  const tableId = `${label}-table`;

  if (groupItems.length === 0) return null;

  return (
    <section className="damage-patterns__group" aria-labelledby={headingId}>
      <button
        type="button"
        className="damage-patterns__group-toggle"
        aria-expanded={expanded}
        aria-controls={tableId}
        onClick={() => setExpanded((current) => !current)}
      >
        <h3 id={headingId}>{title}</h3>
        <span className="damage-patterns__group-count">{groupItems.length}개</span>
        <span className="collapse-arrow" aria-hidden="true">▸</span>
      </button>
      {expanded && (
        <div className="damage-patterns__table" id={tableId} role="table" aria-label={title}>
          <div className="damage-patterns__row damage-patterns__head" role="row">
            <span role="columnheader">피해 유형</span>
            <span role="columnheader">분석 결과</span>
            <span role="columnheader">판단 근거</span>
          </div>
          {groupItems.map((item) => <PatternRow item={item} key={item.pattern_id} />)}
        </div>
      )}
    </section>
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
        initiallyOpen
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
