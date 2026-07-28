// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { DamagePatternTable } from "../../src/features/damage-patterns/DamagePatternTable";
import type { DamagePatternComparisonDto } from "../../src/types/api";

const pattern = (
  overrides: Partial<DamagePatternComparisonDto> = {},
): DamagePatternComparisonDto => ({
  pattern_id: "DP01",
  pattern_name: "소유자 사칭 계약",
  status: "관련 확인 신호 있음",
  reason: "임대인과 등기 소유자 대조가 필요합니다.",
  related_rule_ids: ["R01"],
  related_judgment_ids: ["J01"],
  limitations: "제출 자료 범위에서만 비교합니다.",
  official_sources: [],
  reference_cases: [],
  ...overrides,
});

describe("DamagePatternTable", () => {
  afterEach(cleanup);

  it("shows the linked rule/judgment plain explanation, not the comparison boilerplate", () => {
    render(<DamagePatternTable items={[pattern()]} />);

    fireEvent.click(screen.getByText("근거와 실제 사례"));

    const explanation = screen.getByLabelText("금전 피해와 확인 방법");
    // DP01에 맞는 확인 행동이 들어가야 한다.
    expect(within(explanation).getByText(/소유자 이름을 비교하세요/)).toBeInTheDocument();
    expect(within(explanation).getByText(/위임장·인감증명서/)).toBeInTheDocument();
    // 메타 문구가 조항 설명 자리를 차지하면 안 된다.
    expect(explanation).not.toHaveTextContent("이 비교는 기존 규칙 판정을 피해 유형 관점으로");
    // 금전 문제 자리에는 한계 캐비앗이 아니라 실제 금전 영향이 와야 한다.
    expect(within(explanation).getByText(/돈을 돌려받는 과정이 복잡해질 수 있습니다/)).toBeInTheDocument();
    expect(explanation).not.toHaveTextContent("향후 권리변동이나 제출되지 않은 자료까지 확인한 것은 아닙니다");
  });

  it("falls back to a related rule id when no judgment is linked", () => {
    render(<DamagePatternTable items={[pattern({
      pattern_id: "DP03",
      pattern_name: "보증금 대비 주택가치 확인",
      related_judgment_ids: [],
      related_rule_ids: ["R11", "R20"],
    })]} />);

    fireEvent.click(screen.getByText("근거와 실제 사례"));

    // DP03에 맞는 확인 행동.
    expect(screen.getByText(/주택 시세와 보증금의 비율을 비교하세요/)).toBeInTheDocument();
  });

  it("does not show the removed recent case lookup section", () => {
    render(<DamagePatternTable items={[pattern()]} />);
    fireEvent.click(screen.getByText("근거와 실제 사례"));

    expect(screen.queryByRole("heading", { name: "실제 사례" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "최근 공개 사례 찾기" })).not.toBeInTheDocument();
  });
});
