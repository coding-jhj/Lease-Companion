import { useState } from "react";
import type {
  JudgmentGuidanceDto,
  JudgmentResultDto,
  RuleGuidanceDto,
  RuleResultDto,
  StageGuidanceDto,
  Urgency,
} from "../../types/api";
import { normalizeAction, toPoliteEnding } from "./actionNormalization";

type ResultItem = RuleResultDto | JudgmentResultDto;
type GuidanceItem = RuleGuidanceDto | JudgmentGuidanceDto;

function unique(items: Array<string | null | undefined>) {
  return [...new Set(items.filter((item): item is string => Boolean(item?.trim())))];
}

// 상단에 보여줄 3개가 "번호가 빠른 것"이 아니라 "가장 급한 것"이 되도록
// 시급도로 정렬한다. 낮을수록 위. stageGuidance 항목처럼 시급도가 없는 값은
// 성격에 맞는 기본 시급도를 매긴다.
const URGENCY_RANK: Record<Urgency, number> = {
  "즉시 확인": 0,
  "분석 불가": 1,
  "계약 전 확인": 2,
  "계약 직후 조치": 3,
  "참고": 4,
};

function rankOf(urgency: Urgency | undefined): number {
  return urgency !== undefined ? URGENCY_RANK[urgency] : URGENCY_RANK["참고"];
}

function idOf(item: GuidanceItem): string {
  return "rule_id" in item ? item.rule_id : item.judgment_id;
}

function resultIdOf(item: ResultItem): string {
  return "rule_id" in item ? item.rule_id : item.judgment_id;
}

interface Ranked {
  text: string | null | undefined;
  rank: number;
}

// 시급도순 정렬 + 중복 제거(같은 문구는 더 급한 쪽 rank 유지). 같은 rank는 등장 순서 유지.
function prioritized(entries: Ranked[]): string[] {
  const best = new Map<string, number>();
  for (const { text, rank } of entries) {
    const trimmed = text?.trim();
    if (!trimmed) continue;
    const previous = best.get(trimmed);
    if (previous === undefined || rank < previous) best.set(trimmed, rank);
  }
  return [...best.entries()].sort((a, b) => a[1] - b[1]).map(([text]) => text);
}

function prioritizedPostActions(entries: Ranked[]): string[] {
  const best = new Map<string, { text: string; rank: number }>();
  for (const entry of entries) {
    const trimmed = entry.text?.trim();
    if (!trimmed) continue;
    const canonical = normalizeAction(trimmed, "post_action");
    const previous = best.get(canonical.identity);
    if (previous === undefined || entry.rank < previous.rank) {
      best.set(canonical.identity, { text: canonical.text, rank: entry.rank });
    }
  }
  return [...best.values()].sort((a, b) => a.rank - b.rank).map(({ text }) => text);
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
  const urgencyById = new Map<string, Urgency>();
  for (const item of results) {
    urgencyById.set("rule_id" in item ? item.rule_id : item.judgment_id, item.urgency);
  }
  const guidanceRank = (item: GuidanceItem) => rankOf(urgencyById.get(idOf(item)));

  // 판정상 후속 행동이 필요한 결과만 노출한다. 생성 안내가 있는 판정은 같은
  // 판정의 규칙 원문을 다시 더하지 않아 표현만 다른 중복을 막는다.
  const actionableResults = results.filter((item) => item.triggers_actions);
  const guidedIds = new Set(guidance.map(idOf));
  const unguidedResults = actionableResults.filter((item) => !guidedIds.has(resultIdOf(item)));

  const questions = prioritized([
    ...unguidedResults.map((item) => ({ text: item.question, rank: rankOf(item.urgency) })),
    ...guidance.flatMap((item) => item.questions.map((text) => ({ text, rank: guidanceRank(item) }))),
    ...(stageGuidance?.before_deposit_questions ?? []).map((text) => ({ text, rank: rankOf("계약 전 확인") })),
  ]).map(toPoliteEnding);
  const signingActions = prioritized([
    ...unguidedResults.flatMap((item) => item.recommended_actions.map((text) => ({ text, rank: rankOf(item.urgency) }))),
    ...guidance.flatMap((item) => item.signing_checklist_items.map((entry) => ({ text: entry.text, rank: guidanceRank(item) }))),
    ...(stageGuidance?.signing_checklist ?? []).map((text) => ({ text, rank: rankOf("계약 전 확인") })),
  ]).map(toPoliteEnding);
  const postActions = prioritizedPostActions([
    ...guidance.flatMap((item) => item.post_contract_action_items.map((entry) => ({ text: entry.text, rank: guidanceRank(item) }))),
    ...(stageGuidance?.post_contract_actions ?? []).map((text) => ({ text, rank: rankOf("계약 직후 조치") })),
  ]).map(toPoliteEnding);
  const records = unique(stageGuidance?.record_retention ?? []).map(toPoliteEnding);

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
