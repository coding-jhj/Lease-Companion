import type {
  JudgmentGuidanceDto,
  JudgmentResultDto,
  RuleGuidanceDto,
  RuleResultDto,
  StageGuidanceDto,
  Urgency,
} from "../../types/api";
import {
  cannotJudgeNow,
  displayPriorityForUrgency,
  type DisplayPriority,
} from "../judgment-results/PriorityGroups";

type ResultItem = RuleResultDto | JudgmentResultDto;
type GuidanceItem = RuleGuidanceDto | JudgmentGuidanceDto;

export interface ActionFirstItem {
  id: string;
  title: string;
  reason: string;
  priority: DisplayPriority;
  timing: string;
  questionTarget: "중개사" | "임대인" | "내가 다시 확인";
  question: string | null;
  sourceResult: ResultItem;
}

const PRIORITY_RANK: Record<DisplayPriority, number> = {
  "반드시 확인": 0,
  "확인 권장": 1,
  "일반 확인": 2,
};

function resultId(item: ResultItem): string {
  return "rule_id" in item ? item.rule_id : item.judgment_id;
}

function resultTitle(item: ResultItem): string {
  return "rule_name" in item ? item.rule_name : item.judgment_name;
}

function guidanceId(item: GuidanceItem): string {
  return "rule_id" in item ? item.rule_id : item.judgment_id;
}

// 생성 문구는 "제목: 제목을 확인합니다. 결과: X. 공식 근거와 함께 확인해 주세요." 형태가 많다.
// 제목은 카드 heading에, 상태는 상태 배지에 이미 있으므로 본문에서만 덜어낸다.
// 패턴이 없으면 원문을 그대로 둔다(규칙 원문 reason은 문장 구조가 다르다).
const TRAILING_NOTE = "공식 근거와 함께 확인해 주세요.";
const RESULT_SENTENCE = /\s*결과:\s*[^.]*\.\s*$/;

export function cleanReason(title: string, reason: string): string {
  const original = reason.trim();
  let text = original;
  if (text.startsWith(title)) {
    const rest = text.slice(title.length).replace(/^\s*[:：]\s*/, "").trim();
    if (rest) text = rest;
  }
  if (text.endsWith(TRAILING_NOTE)) {
    text = text.slice(0, -TRAILING_NOTE.length).trim();
  }
  const withoutResult = text.replace(RESULT_SENTENCE, "").trim();
  if (withoutResult) text = withoutResult;
  return text || original;
}

function timingFor(urgency: Urgency, stageGuidance: StageGuidanceDto | null): string {
  if (stageGuidance?.contract_context.contract_stage === "계약 직후") {
    return urgency === "참고" ? "계약 후 다시 확인" : "계약 후 지금 확인";
  }
  if (urgency === "계약 직후 조치") return "계약 직후 확인";
  if (urgency === "참고") {
    return "계약 과정에서 확인";
  }
  return "서명·송금 전에 확인";
}

export function questionTargetFor(text: string | null): ActionFirstItem["questionTarget"] {
  if (!text) return "내가 다시 확인";
  const compact = text.replace(/\s+/g, "");
  if (/중개사|공인중개사|중개대상물/.test(compact)) return "중개사";
  if (/임대인|소유자|계약상대|계좌명의|공동소유|대리인|보증금반환|수리|관리비/.test(compact)) {
    return "임대인";
  }
  return "내가 다시 확인";
}

export function buildActionFirstItems(
  results: ResultItem[],
  guidance: GuidanceItem[],
  stageGuidance: StageGuidanceDto | null = null,
): ActionFirstItem[] {
  const guidanceById = new Map(guidance.map((item) => [guidanceId(item), item]));

  return results
    .filter((item) => !cannotJudgeNow(item))
    .map((sourceResult) => {
      const id = resultId(sourceResult);
      const matchingGuidance = guidanceById.get(id);
      const question = matchingGuidance?.questions.find((item) => item.trim())?.trim() ?? null;
      const priority = displayPriorityForUrgency(sourceResult.urgency);
      const title = resultTitle(sourceResult);
      return {
        id,
        title,
        reason: cleanReason(title, matchingGuidance?.explanation.trim() || sourceResult.reason),
        priority,
        timing: timingFor(sourceResult.urgency, stageGuidance),
        questionTarget: questionTargetFor(question),
        question,
        sourceResult,
      };
    })
    .sort((left, right) => PRIORITY_RANK[left.priority] - PRIORITY_RANK[right.priority]);
}
