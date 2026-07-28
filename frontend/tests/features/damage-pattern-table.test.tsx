// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
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
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("shows the linked rule/judgment plain explanation, not the comparison boilerplate", () => {
    render(<DamagePatternTable items={[pattern()]} />);

    fireEvent.click(screen.getByText("근거와 실제 사례"));

    const explanation = screen.getByLabelText("쉬운 설명과 돈에 미치는 영향");
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

    fireEvent.click(screen.getByText("근거와 실제 사례"));

    // DP03 → R11 큐레이션 설명.
    expect(screen.getByText(/보증금이 집 시세 대비 어느 정도인지/)).toBeInTheDocument();
  });

  it("loads up to two recent HUG press releases only after the user clicks", async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({
      pattern_id: "DP01",
      items: [
        {
          title: "HUG, 전세사기 위험 정보 개방한다",
          publisher: "주택도시보증공사(HUG)",
          published_at: "2026-07-15",
          source_url: "https://www.khug.or.kr/khmb/m/hs/nd/hsnd000002.jsp?idx=37967",
        },
        {
          title: "전세사기 피해지원 및 예방 확대 업무협약",
          publisher: "주택도시보증공사(HUG)",
          published_at: "2026-06-10",
          source_url: "https://www.khug.or.kr/khmb/m/hs/nd/hsnd000002.jsp?idx=37757",
        },
      ],
      retrieved_at: "2026-07-28T00:00:00Z",
      notice: "외부 공개 보도자료이며 현재 계약의 판정 근거가 아닙니다.",
    }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }));
    vi.stubGlobal("fetch", fetchMock);
    render(<DamagePatternTable items={[pattern()]} />);
    fireEvent.click(screen.getByText("근거와 실제 사례"));

    expect(screen.getByText(/‘소유자 사칭 계약’과 관련된/)).toBeInTheDocument();
    expect(screen.queryByText("HUG, 전세사기 위험 정보 개방한다")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "최근 공개 사례 찾기" }));

    const firstTitle = await screen.findByText("HUG, 전세사기 위험 정보 개방한다");
    expect(firstTitle).toBeInTheDocument();
    expect(screen.getByText("전세사기 피해지원 및 예방 확대 업무협약")).toBeInTheDocument();
    const links = screen.getAllByRole("link", { name: /보도자료 출처 열기/ });
    expect(links).toHaveLength(2);
    expect(links[0]).toHaveAttribute("href", expect.stringContaining("khug.or.kr"));
    expect(screen.getByText(/현재 계약의 판정 근거가 아닙니다/)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/public-cases/recent-press-releases?pattern_id=DP01",
      expect.any(Object),
    );
  });
});
