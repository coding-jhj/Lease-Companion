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
      return {
        id,
        title: resultTitle(sourceResult),
        reason: matchingGuidance?.explanation.trim() || sourceResult.reason,
        priority,
        timing: timingFor(sourceResult.urgency, stageGuidance),
        questionTarget: questionTargetFor(question),
        question,
        sourceResult,
      };
    })
    .sort((left, right) => PRIORITY_RANK[left.priority] - PRIORITY_RANK[right.priority]);
}
