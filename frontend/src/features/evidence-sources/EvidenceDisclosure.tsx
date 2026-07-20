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
          <summary>근거 요약 자세히 보기</summary>
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
  idPrefix,
}: {
  sources: OfficialSourceDto[];
  limitations: string;
  idPrefix: string;
}) {
  const evidenceTitleId = `${idPrefix}-official-evidence-title`;
  const limitationTitleId = `${idPrefix}-limitation-title`;

  return (
    <div className="evidence-disclosure">
      <section className="evidence-disclosure__sources" aria-labelledby={evidenceTitleId}>
        <div className="evidence-disclosure__intro">
          <div>
            <strong id={evidenceTitleId}>공식 근거</strong>
            <p>
              {sources.length > 0
                ? "이 판정에 참고한 공공기관 자료입니다. 제목을 먼저 확인하고 필요한 내용만 펼쳐보세요."
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
      <aside className="limitation-card" aria-labelledby={limitationTitleId}>
        <strong id={limitationTitleId}>이 판정에서 알아둘 점</strong>
        <p>{limitations}</p>
      </aside>
    </div>
  );
}
