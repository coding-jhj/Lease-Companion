import { useEffect, useState } from "react";
import { mvpService } from "../../services/mvpService";
import type { RecentPressReleaseResponseDto } from "../../types/api";

type LookupState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "success"; result: RecentPressReleaseResponseDto }
  | { status: "error" };

export function RecentPressReleaseLookup({
  idPrefix,
  patternId,
  patternName,
}: {
  idPrefix: string;
  patternId: string;
  patternName: string;
}) {
  const [state, setState] = useState<LookupState>({ status: "idle" });

  useEffect(() => {
    setState({ status: "idle" });
  }, [patternId]);

  const findRecentCases = async () => {
    setState({ status: "loading" });
    try {
      const result = await mvpService.getRecentPressReleases(patternId);
      if (result.pattern_id !== patternId) {
        setState({ status: "error" });
        return;
      }
      setState({ status: "success", result });
    } catch {
      setState({ status: "error" });
    }
  };
  const hasMatchingResult = (
    state.status === "success" && state.result.pattern_id === patternId
  );

  return (
    <section className="recent-press-release" aria-labelledby={`${idPrefix}-recent-press-release-title`}>
      <div className="recent-press-release__heading">
        <div>
          <h3 id={`${idPrefix}-recent-press-release-title`}>실제 사례</h3>
          <p>HUG와 국토교통부에서 ‘{patternName}’과 관련된 최신 보도자료를 찾습니다.</p>
        </div>
        <button
          type="button"
          className="secondary-button recent-press-release__button"
          onClick={findRecentCases}
          disabled={state.status === "loading"}
        >
          {state.status === "loading" ? "찾는 중…" : "최근 공개 사례 찾기"}
        </button>
      </div>

      <div aria-live="polite">
        {hasMatchingResult && state.result.items.length === 0 && (
          <p className="empty-note">관련된 최신 보도자료를 찾지 못했습니다.</p>
        )}
        {hasMatchingResult && state.result.items.length > 0 && (
          <>
            <ul className="recent-press-release__list">
              {state.result.items.map((item) => (
                <li key={item.source_url}>
                  <strong>{item.title}</strong>
                  <span>{item.publisher} · {item.published_at}</span>
                  <a href={item.source_url} target="_blank" rel="noreferrer">
                    보도자료 출처 열기 <span aria-hidden="true">↗</span>
                  </a>
                </li>
              ))}
            </ul>
            <p className="recent-press-release__notice">{state.result.notice}</p>
          </>
        )}
        {state.status === "error" && (
          <p className="inline-error" role="alert">
            공개 보도자료를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.
          </p>
        )}
      </div>
    </section>
  );
}
