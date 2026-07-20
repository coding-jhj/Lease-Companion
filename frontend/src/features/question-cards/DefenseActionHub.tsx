import { useState } from "react";
import type {
  JudgmentGuidanceDto,
  JudgmentResultDto,
  RuleGuidanceDto,
  RuleResultDto,
  StageGuidanceDto,
} from "../../types/api";

type ResultItem = RuleResultDto | JudgmentResultDto;
type GuidanceItem = RuleGuidanceDto | JudgmentGuidanceDto;

function unique(items: Array<string | null | undefined>) {
  return [...new Set(items.filter((item): item is string => Boolean(item?.trim())))];
}

const INITIAL_ACTION_COUNT = 3;

function ActionList({
  title,
  description,
  items,
  collapsible = false,
}: {
  title: string;
  description: string;
  items: string[];
  collapsible?: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const hiddenCount = Math.max(0, items.length - INITIAL_ACTION_COUNT);
  const visibleItems = collapsible && !expanded ? items.slice(0, INITIAL_ACTION_COUNT) : items;

  return (
    <section className="action-hub__group">
      <h3>{title}</h3>
      <p>{description}</p>
      {items.length > 0
        ? <>
          <ul>{visibleItems.map((item) => <li key={item}>{item}</li>)}</ul>
          {collapsible && hiddenCount > 0 && (
            <button className="text-button action-hub__more" type="button" onClick={() => setExpanded((current) => !current)}>
              {expanded ? "접기" : `${hiddenCount}개 더 보기`}
            </button>
          )}
        </>
        : <p className="action-hub__empty">현재 추가로 안내할 내용이 없습니다.</p>}
    </section>
  );
}

export function DefenseActionHub({
  results,
  guidance,
  stageGuidance,
}: {
  results: ResultItem[];
  guidance: GuidanceItem[];
  stageGuidance: StageGuidanceDto | null;
}) {
  const questions = unique([
    ...results.map((item) => item.question),
    ...guidance.flatMap((item) => item.questions),
    ...(stageGuidance?.before_deposit_questions ?? []),
  ]);
  const signingActions = unique([
    ...results.flatMap((item) => item.recommended_actions),
    ...guidance.flatMap((item) => item.signing_checklist_items.map((entry) => entry.text)),
    ...(stageGuidance?.signing_checklist ?? []),
  ]);
  const postActions = unique([
    ...guidance.flatMap((item) => item.post_contract_action_items.map((entry) => entry.text)),
    ...(stageGuidance?.post_contract_actions ?? []),
  ]);
  const records = unique(stageGuidance?.record_retention ?? []);

  return (
    <section className="action-hub" aria-labelledby="action-hub-title">
      <header className="action-hub__header">
        <p>나를 지키는 다음 단계</p>
        <h2 id="action-hub-title">방어 행동 허브</h2>
        <span>같은 내용은 한 번만 모아 보여드립니다.</span>
      </header>
      <div className="action-hub__grid">
        <ActionList collapsible title="먼저 물어볼 질문" description="입금이나 서명 전에 상대방에게 확인하세요." items={questions} />
        <ActionList collapsible title="서명 전 확인 행동" description="문서와 조건을 직접 대조할 항목입니다." items={signingActions} />
        <ActionList collapsible title="계약 직후 행동" description="임차권을 지키기 위해 이어서 처리하세요." items={postActions} />
        <ActionList title="보관할 자료" description="나중에 다시 확인할 수 있도록 남겨두세요." items={records} />
      </div>
    </section>
  );
}
