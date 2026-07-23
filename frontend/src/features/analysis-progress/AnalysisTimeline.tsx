export type AnalysisStage = "request" | "analysis" | "generation" | "complete";

const stages: Array<{ id: AnalysisStage; title: string; description: string }> = [
  { id: "request", title: "결과 준비 요청 접수", description: "확인한 계약 정보를 결과 준비 단계로 전달합니다." },
  { id: "analysis", title: "규칙 판정·공식 근거 정리", description: "규칙 결과와 연결 가능한 공식 자료를 함께 정리합니다." },
  { id: "generation", title: "질문·행동 안내 생성", description: "확인 질문과 서명 전·계약 직후 행동을 준비합니다." },
  { id: "complete", title: "확인 결과 준비 완료", description: "확인 결과와 다음 행동을 확인할 수 있습니다." },
];

const stateLabels = {
  complete: "완료",
  current: "진행 중",
  upcoming: "대기",
  error: "확인 필요",
} as const;

export function AnalysisTimeline({
  activeStage,
  hasError = false,
  delayed = false,
}: {
  activeStage: AnalysisStage;
  hasError?: boolean;
  delayed?: boolean;
}) {
  const activeIndex = stages.findIndex((stage) => stage.id === activeStage);

  return (
    <section className="analysis-timeline" aria-labelledby="analysis-timeline-title">
      <div className="analysis-timeline__heading">
        <p>현재 처리 단계</p>
        <h2 id="analysis-timeline-title">확인 결과 준비 상황</h2>
      </div>
      <ol>
        {stages.map((stage, index) => {
          const state = index < activeIndex
            ? "complete"
            : index === activeIndex
              ? hasError ? "error" : "current"
              : "upcoming";
          const label = state === "current" && delayed ? "확인 지연" : stateLabels[state];
          return (
            <li
              className={`analysis-timeline__step analysis-timeline__step--${state}`}
              aria-current={state === "current" || state === "error" ? "step" : undefined}
              key={stage.id}
            >
              <span className="analysis-timeline__marker" aria-hidden="true">
                {state === "complete" ? "✓" : index + 1}
              </span>
              <div>
                <div className="analysis-timeline__title-row">
                  <h3>{stage.title}</h3>
                  <span>{label}</span>
                </div>
                <p>{stage.description}</p>
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
