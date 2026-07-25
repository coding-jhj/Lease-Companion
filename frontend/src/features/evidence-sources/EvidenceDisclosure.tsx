import type { OfficialSourceDto } from "../../types/api";

const SECTION_HEADING_PATTERN = /^\[[^\]]+\]$/;
const ARTICLE_PATTERN = /^(제\d+조(?:의\d+)?(?:\([^)]*\))?)\s*(.*)$/;
const BULLET_PATTERN = /^[·•]\s*(.*)$/;

const PREVIEW_LINE_COUNT = 3;

function EvidenceSummary({ summary }: { summary: string }) {
  const allLines = summary
    .replace(/\r\n?/g, "\n")
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
  // "# 기관:", "# 출처:" 같은 자료 표기는 조문과 분리해 접는다.
  const metaLines = allLines.filter((line) => line.startsWith("#"));
  const bodyLines = allLines.filter((line) => !line.startsWith("#"));
  const previewLines = bodyLines.slice(0, PREVIEW_LINE_COUNT);
  const restLines = bodyLines.slice(PREVIEW_LINE_COUNT);

  return (
    <>
      {renderLines(previewLines, "evidence-summary__content")}
      {restLines.length > 0 && (
        <details className="evidence-summary__more">
          <summary>원문 더 보기 ({restLines.length}줄)</summary>
          {renderLines(restLines, "evidence-summary__content evidence-summary__rest")}
        </details>
      )}
      {metaLines.length > 0 && (
        <details className="evidence-summary__meta">
          <summary>자료 정보 ({metaLines.length}줄)</summary>
          {renderLines(metaLines, "evidence-summary__content evidence-summary__rest")}
        </details>
      )}
    </>
  );
}

function renderLines(lines: string[], className: string) {
  return (
    <div className={className}>
      {lines.map((line, index) => {
        if (SECTION_HEADING_PATTERN.test(line)) {
          return <h5 key={`${index}-${line}`}>{line}</h5>;
        }

        const bullet = line.match(BULLET_PATTERN);
        if (bullet) {
          return (
            <p className="evidence-summary__bullet" key={`${index}-${line}`}>
              <span aria-hidden="true">·</span>
              <span>{bullet[1]}</span>
            </p>
          );
        }

        const article = line.match(ARTICLE_PATTERN);
        if (article) {
          return (
            <p className="evidence-summary__article" key={`${index}-${line}`}>
              <strong>{article[1]}</strong>{article[2] ? ` ${article[2]}` : ""}
            </p>
          );
        }

        return <p key={`${index}-${line}`}>{line}</p>;
      })}
    </div>
  );
}

function EvidenceSourceCard({ source, index }: { source: OfficialSourceDto; index: number }) {
  const relatedExcerpt = source.summary?.trim() || null;

  return (
    <section className="evidence-source-card">
      <div className="evidence-source-card__meta">
        <span className="evidence-source-badge">공식자료 {index + 1}</span>
        <span>{source.institution}</span>
      </div>
      <h4>{source.title}</h4>
      {source.article_or_section && <p className="evidence-source-section">{source.article_or_section}</p>}
      {relatedExcerpt ? (
        <section className="evidence-related" aria-label="이번 판정과 연결된 공식 근거">
          <strong>이번 판정과 연결된 근거</strong>
          <EvidenceSummary summary={relatedExcerpt} />
        </section>
      ) : (
        <p className="evidence-summary-empty">이번 판정과 연결된 공식자료 발췌가 없습니다.</p>
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
  financialImpactLabel = "돈에 미치는 영향",
  idPrefix,
  order = "explanation-first",
}: {
  sources: OfficialSourceDto[];
  limitations: string;
  explanation: string;
  financialImpact: string;
  financialImpactLabel?: string;
  idPrefix: string;
  order?: "sources-first" | "explanation-first";
}) {
  const evidenceTitleId = `${idPrefix}-official-evidence-title`;
  const explanationTitleId = `${idPrefix}-plain-explanation-title`;
  const limitationTitleId = `${idPrefix}-limitation-title`;

  const sourceSection = (
    <details className="evidence-disclosure__sources" aria-labelledby={evidenceTitleId}>
        {/* 펼치기 버튼이 하는 일을 문장으로 다시 쓰지 않는다. 제목 + 건수만 남긴다. */}
        <summary className="evidence-disclosure__intro">
          <strong id={evidenceTitleId}>공식자료</strong>
          <span className="evidence-count" aria-label={`공식자료 ${sources.length}건`}>{sources.length}건</span>
          <span className="collapse-arrow" aria-hidden="true">▸</span>
        </summary>
        <div className="evidence-disclosure__sources-body">
        {sources.length > 0 ? (
          <div className="evidence-source-list">
            {sources.map((source, index) => (
              <EvidenceSourceCard source={source} index={index} key={source.source_id} />
            ))}
          </div>
        ) : (
          <p className="evidence-empty">공식 근거가 없는 항목은 계약 상대방이나 관련 기관에 직접 확인해 주세요.</p>
        )}
        </div>
    </details>
  );
  // 카드 본문과 같은 내용을 "조항을 쉽게 설명하면" 소제목으로 한 번 더 쓰지 않는다.
  const explanationSection = (
    <section className="plain-evidence-card" aria-label="쉬운 설명과 돈에 미치는 영향">
        <div className="plain-evidence-card__explanation">
          <p id={explanationTitleId}>{explanation}</p>
        </div>
        <div className="financial-impact">
          <span className="financial-impact__icon" aria-hidden="true">!</span>
          <div>
            <strong>{financialImpactLabel}</strong>
            <p>{financialImpact}</p>
          </div>
        </div>
    </section>
  );

  return (
    <div className="evidence-disclosure">
      {order === "explanation-first" ? <>{explanationSection}{sourceSection}</> : <>{sourceSection}{explanationSection}</>}
      <aside className="limitation-card" aria-labelledby={limitationTitleId}>
        <strong id={limitationTitleId}>확인 한계</strong>
        <p>{limitations}</p>
      </aside>
    </div>
  );
}
