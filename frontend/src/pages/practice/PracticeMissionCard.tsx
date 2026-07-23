import { practiceMissionForScenario } from "./practiceMissionCatalog";

export function PracticeMissionCard({
  scenarioId,
  confirmedCount,
}: {
  scenarioId: string;
  confirmedCount?: number;
}) {
  const mission = practiceMissionForScenario(scenarioId);
  const confirmed = confirmedCount ?? 0;
  const active = confirmedCount !== undefined;
  // 공개 목표 수가 있는 시나리오만 분모·진행바를 표시한다. 목표 수가 없으면
  // 잘못된 기본값으로 100%처럼 보이지 않게 확인 개수만 안내한다.
  const hasTarget = mission.targetCount !== null;
  const progress = hasTarget ? Math.min(mission.targetCount as number, confirmed) : confirmed;

  return (
    <section className="practice-mission-card" aria-labelledby="practice-mission-title">
      <div className="practice-mission-card__heading">
        <div>
          <p>오늘의 미션</p>
          <h2 id="practice-mission-title">{mission.title}</h2>
        </div>
        {active && (hasTarget
          ? <strong>{progress} / {mission.targetCount}</strong>
          : <strong>{confirmed}개 확인</strong>)}
      </div>
      <p>{mission.description}</p>
      {active && hasTarget && (
        <div
          className="practice-mission-progress"
          role="progressbar"
          aria-label="미션 진행률"
          aria-valuemin={0}
          aria-valuemax={mission.targetCount as number}
          aria-valuenow={progress}
        >
          <span style={{ width: `${(progress / (mission.targetCount as number)) * 100}%` }} />
        </div>
      )}
      <small>{mission.guide}</small>
    </section>
  );
}
