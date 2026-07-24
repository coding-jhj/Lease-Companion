import { useState } from "react";
import type {
  JudgmentGuidanceDto,
  JudgmentResultDto,
  RuleGuidanceDto,
  RuleResultDto,
  StageGuidanceDto,
  Urgency,
} from "../../types/api";
import {
  questionTargetFor,
  type ActionFirstItem,
} from "../result-report/actionFirstViewModel";
import { normalizeAction, toPoliteEnding } from "./actionNormalization";

export type DefenseResultItem = RuleResultDto | JudgmentResultDto;
export type DefenseGuidanceItem = RuleGuidanceDto | JudgmentGuidanceDto;
export type QuestionGroups = Record<ActionFirstItem["questionTarget"], string[]>;

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

function idOf(item: DefenseGuidanceItem): string {
  return "rule_id" in item ? item.rule_id : item.judgment_id;
}

function resultIdOf(item: DefenseResultItem): string {
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
  copyable = false,
}: {
  title: string;
  description: string;
  items: string[];
  collapsible?: boolean;
  copyable?: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const [copiedQuestion, setCopiedQuestion] = useState<string | null>(null);
  const [copyError, setCopyError] = useState(false);
  const hiddenCount = Math.max(0, items.length - INITIAL_ACTION_COUNT);
  const visibleItems = collapsible && !expanded ? items.slice(0, INITIAL_ACTION_COUNT) : items;

  async function copyQuestion(question: string) {
    setCopiedQuestion(null);
    setCopyError(false);
    try {
      await navigator.clipboard.writeText(question);
      setCopiedQuestion(question);
    } catch {
      setCopyError(true);
    }
  }

  return (
    <section className="action-hub__group">
      <h3>{title}</h3>
      <p>{description}</p>
      {items.length > 0
        ? <>
          <ul>{visibleItems.map((item) => (
            <li className={copyable ? "action-hub__question" : undefined} key={item}>
              <span>{item}</span>
              {copyable && (
                <button
                  className="text-button action-hub__copy"
                  type="button"
                  aria-label={`질문 복사: ${item}`}
                  onClick={() => void copyQuestion(item)}
                >
                  복사
                </button>
              )}
            </li>
          ))}</ul>
          {collapsible && hiddenCount > 0 && (
            <button className="text-button action-hub__more" type="button" onClick={() => setExpanded((current) => !current)}>
              {expanded ? "접기" : `${hiddenCount}개 더 보기`}
            </button>
          )}
          {copiedQuestion && <p className="action-hub__copy-status" role="status">복사했습니다.</p>}
          {copyError && <p className="action-hub__copy-error" role="alert">복사하지 못했습니다. 질문을 직접 선택해 복사해 주세요.</p>}
        </>
        : <p className="action-hub__empty">현재 추가로 안내할 내용이 없습니다.</p>}
    </section>
  );
}

export function buildQuestionGroups(
  results: DefenseResultItem[],
  guidance: DefenseGuidanceItem[],
  stageGuidance: StageGuidanceDto | null,
): QuestionGroups {
  const urgencyById = new Map<string, Urgency>();
  for (const item of results) {
    urgencyById.set(resultIdOf(item), item.urgency);
  }
  const guidanceRank = (item: DefenseGuidanceItem) => rankOf(urgencyById.get(idOf(item)));
  const guidedIds = new Set(guidance.map(idOf));
  const fallbackResults = results.filter((item) => item.triggers_actions && !guidedIds.has(resultIdOf(item)));
  const questions = prioritized([
    ...fallbackResults.map((item) => ({ text: item.question, rank: rankOf(item.urgency) })),
    ...guidance.flatMap((item) => item.questions.map((text) => ({ text, rank: guidanceRank(item) }))),
    ...guidance.flatMap((item) => (item.request_templates ?? []).map((text) => ({ text, rank: guidanceRank(item) }))),
    ...(stageGuidance?.before_deposit_questions ?? []).map((text) => ({ text, rank: rankOf("계약 전 확인") })),
  ].map((entry) => ({
    ...entry,
    text: entry.text ? toPoliteEnding(entry.text) : entry.text,
  })));
  const groups: QuestionGroups = {
    "중개사": [],
    "임대인": [],
    "내가 다시 확인": [],
  };
  for (const question of questions) groups[questionTargetFor(question)].push(question);
  return groups;
}

export function DefenseActionHub({
  results,
  guidance,
  stageGuidance,
}: {
  results: DefenseResultItem[];
  guidance: DefenseGuidanceItem[];
  stageGuidance: StageGuidanceDto | null;
}) {
  const urgencyById = new Map<string, Urgency>();
  for (const item of results) {
    urgencyById.set("rule_id" in item ? item.rule_id : item.judgment_id, item.urgency);
  }
  const guidanceRank = (item: DefenseGuidanceItem) => rankOf(urgencyById.get(idOf(item)));

  // 판정상 후속 행동이 필요한 결과만 노출한다. 생성 안내가 있는 판정은 같은
  // 판정의 규칙 원문을 다시 더하지 않아 표현만 다른 중복을 막는다.
  const actionableResults = results.filter((item) => item.triggers_actions);
  const guidedIds = new Set(guidance.map(idOf));
  const unguidedResults = actionableResults.filter((item) => !guidedIds.has(resultIdOf(item)));

  const questionsByTarget = buildQuestionGroups(results, guidance, stageGuidance);
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
  const beforeContract = unique(stageGuidance?.before_contract_actions ?? signingActions).map(toPoliteEnding);
  const duringContract = unique(stageGuidance?.during_contract_actions ?? signingActions).map(toPoliteEnding);
  const closingDay = unique(stageGuidance?.closing_day_actions ?? []).map(toPoliteEnding);
  const afterContract = unique(stageGuidance?.after_contract_actions ?? postActions).map(toPoliteEnding);
  return (
    <>
      <section className="action-hub" aria-labelledby="action-hub-title">
        <header className="action-hub__header">
          <p>그대로 읽거나 복사해 물어보세요</p>
          <h2 id="action-hub-title">상대방에게 물어볼 말</h2>
          <span>같은 문구는 한 번만 보여드리며, 확인할 대상을 나눠 정리했습니다.</span>
        </header>
        <div className="action-hub__grid">
          <ActionList copyable collapsible title="중개사에게 물어볼 말" description="문서와 중개 설명이 맞는지 확인하세요." items={questionsByTarget["중개사"]} />
          <ActionList copyable collapsible title="임대인에게 물어볼 말" description="계약 권한과 금액·조건을 직접 확인하세요." items={questionsByTarget["임대인"]} />
          <ActionList copyable collapsible title="내가 문서에서 다시 볼 것" description="계약서와 확인 자료를 직접 대조하세요." items={questionsByTarget["내가 다시 확인"]} />
        </div>
      </section>
      <section className="stage-guidance" aria-labelledby="stage-guidance-title">
        <div className="section-heading">
          <p>계약 진행 순서에 맞춰 이어서 확인하세요</p>
          <h2 id="stage-guidance-title">계약 단계별 행동</h2>
        </div>
        <div className="stage-guidance__grid">
          <ActionList collapsible title="계약 전" description="계약 상대와 문서·권리관계를 먼저 확인하세요." items={beforeContract} />
          <ActionList collapsible title="계약 중" description="서명할 계약서 문구와 조건을 확인하세요." items={duringContract} />
          <ActionList collapsible title="잔금·입주 당일" description="송금과 입주 직전에 다시 확인하세요." items={closingDay} />
          <ActionList collapsible title="계약 후" description="임차권 확보와 자료 보관을 이어서 처리하세요." items={afterContract} />
          <ActionList title="보관할 자료" description="나중에 다시 확인할 수 있도록 남겨두세요." items={records} />
        </div>
      </section>
    </>
  );
}
