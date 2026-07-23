import { practiceMissionForScenario } from "./practiceMissionCatalog";

export function PracticeMissionCard({
  scenarioId,
  confirmedCount,
}: {
  scenarioId: string;
  confirmedCount?: number;
}) {
  const mission = practiceMissionForScenario(scenarioId);
  const progress = Math.min(mission.targetCount, confirmedCount ?? 0);
  const active = confirmedCount !== undefined;

  return (
    <section className="practice-mission-card" aria-labelledby="practice-mission-title">
      <div className="practice-mission-card__heading">
        <div>
          <p>오늘의 미션</p>
          <h2 id="practice-mission-title">{mission.title}</h2>
        </div>
        {active && <strong>{progress} / {mission.targetCount}</strong>}
      </div>
      <p>{mission.description}</p>
      {active && (
        <div
          className="practice-mission-progress"
          role="progressbar"
          aria-label="미션 진행률"
          aria-valuemin={0}
          aria-valuemax={mission.targetCount}
          aria-valuenow={progress}
        >
          <span style={{ width: `${(progress / mission.targetCount) * 100}%` }} />
        </div>
      )}
      <small>{mission.guide}</small>
    </section>
  );
}
