import type { OfficialSourceDto } from "../../types/api";

function EvidenceSourceCard({ source, index }: { source: OfficialSourceDto; index: number }) {
  return (
    <section className="evidence-source-card">
      <div className="evidence-source-card__meta">
        <span className="evidence-source-badge">공식자료 {index + 1}</span>
        <span>{source.institution}</span>
      </div>
      <h4>{source.title}</h4>
      {source.summary ? (
        <details className="evidence-summary">
          <summary>공식자료 내용 전체 보기</summary>
          <p>{source.summary}</p>
        </details>
      ) : (
        <p className="evidence-summary-empty">제공된 요약이 없습니다. 공식 원문에서 내용을 확인해 주세요.</p>
      )}
      {source.source_url && (
        <a
          className="evidence-source-link"
          href={source.source_url}
          target="_blank"
          rel="noreferrer"
        >
          공식 원문 열기 <span aria-hidden="true">↗</span>
        </a>
      )}
    </section>
  );
}

export function EvidenceDisclosure({
  sources,
  limitations,
  explanation,
  financialImpact,
  idPrefix,
}: {
  sources: OfficialSourceDto[];
  limitations: string;
  explanation: string;
  financialImpact: string;
  idPrefix: string;
}) {
  const evidenceTitleId = `${idPrefix}-official-evidence-title`;
  const explanationTitleId = `${idPrefix}-plain-explanation-title`;
  const limitationTitleId = `${idPrefix}-limitation-title`;

  return (
    <div className="evidence-disclosure">
      <section className="evidence-disclosure__sources" aria-labelledby={evidenceTitleId}>
        <div className="evidence-disclosure__intro">
          <div>
            <strong id={evidenceTitleId}>공식 근거</strong>
            <p>
              {sources.length > 0
                ? "어려운 법률 문장 대신 핵심 의미와 생길 수 있는 금전 문제를 먼저 정리했습니다."
                : "현재 연결된 공식 근거가 없습니다."}
            </p>
          </div>
          <span className="evidence-count" aria-label={`공식 근거 ${sources.length}건`}>{sources.length}건</span>
        </div>
        {sources.length > 0 ? (
          <div className="evidence-source-list">
            {sources.map((source, index) => (
              <EvidenceSourceCard source={source} index={index} key={source.source_id} />
            ))}
          </div>
        ) : (
          <p className="evidence-empty">공식 근거가 없는 항목은 계약 상대방이나 관련 기관에 직접 확인해 주세요.</p>
        )}
      </section>
      <section className="plain-evidence-card" aria-labelledby={explanationTitleId}>
        <div className="plain-evidence-card__explanation">
          <strong id={explanationTitleId}>조항을 쉽게 설명하면</strong>
          <p>{explanation}</p>
        </div>
        <div className="financial-impact">
          <span className="financial-impact__icon" aria-hidden="true">!</span>
          <div>
            <strong>생길 수 있는 금전 문제</strong>
            <p>{financialImpact}</p>
          </div>
        </div>
      </section>
      <aside className="limitation-card" aria-labelledby={limitationTitleId}>
        <strong id={limitationTitleId}>이 판정에서 알아둘 점</strong>
        <p>{limitations}</p>
      </aside>
    </div>
  );
}
