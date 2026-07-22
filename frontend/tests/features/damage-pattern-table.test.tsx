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

    fireEvent.click(screen.getByText("근거와 분석 한계"));

    const explanation = screen.getByText("조항을 쉽게 설명하면").closest("section")!;
    // DP01 → J01 큐레이션 설명이 들어가야 한다.
    expect(within(explanation).getByText(/등기사항증명서에 적힌 소유자와 같은 사람인지/)).toBeInTheDocument();
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

    fireEvent.click(screen.getByText("근거와 분석 한계"));

    // DP03 → R11 큐레이션 설명.
    expect(screen.getByText(/보증금이 집 시세 대비 어느 정도인지/)).toBeInTheDocument();
  });
});
