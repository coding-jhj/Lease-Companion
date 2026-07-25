/// <reference types="vite/client" />

declare module "virtual:practice-semantic-rules" {
  interface DeterministicSemanticRule {
    rule_id: string;
    turn_id: string;
    answer_category: "appropriate_check" | "avoidance";
    all_of_keyword_groups: string[][];
    none_of_keywords: string[];
  }

  interface PracticeEndingReport {
    title: string;
    feedback_label: string;
    feedback: string;
    practice_phrase: string;
    action_summary: [string, string, string];
  }

  interface PracticeDebriefRules {
    defensive_stop_action_ids: string[];
    ending_reports: Record<
      "rights_asserted" | "insufficient_protection" | "transaction_stopped",
      PracticeEndingReport
    >;
  }

  const rules: Record<string, DeterministicSemanticRule[]>;
  export const debriefByScenario: Record<string, PracticeDebriefRules>;
  export default rules;
}
