// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { GuidedReviewCard } from "../../src/features/extraction-review/GuidedReviewCard";
import type { ReviewQueueItem } from "../../src/features/extraction-review/reviewQueue";

function item(fieldName = "deposit", formattedValue = "10,000,000"): ReviewQueueItem {
  return {
    key: `contract:${fieldName}`,
    fieldName,
    title: fieldName === "special_clauses" ? "특약 내용" : "보증금",
    prompt: "계약서와 같나요?",
    view: {
      key: `contract:${fieldName}`,
      document_type: "contract",
      label: fieldName === "special_clauses" ? "특약사항" : "보증금",
      formattedValue,
      editor: fieldName === "special_clauses" ? "clause-list" : "scalar",
      guidance: null,
      field: {
        field_name: fieldName,
        extracted_value: formattedValue,
        normalized_value: formattedValue,
        user_corrected_value: null,
        verification_status: "unverified",
        confidence: "추출됨",
        source_evidence: { page: 1, text: "문서 원문" },
        issue_code: null,
        failure_reason: null,
      },
    },
  };
}

function renderCard(overrides: Partial<React.ComponentProps<typeof GuidedReviewCard>> = {}) {
  const props = {
    item: item(),
    draftValue: undefined,
    busy: false,
    onConfirm: vi.fn(),
    onChange: vi.fn(),
    onCannotVerify: vi.fn(),
    ...overrides,
  };
  return { ...props, ...render(<GuidedReviewCard {...props} />) };
}

describe("GuidedReviewCard", () => {
  it("기본 상태에서 확인·수정·확인 불가 행동을 제공한다", () => {
    renderCard();

    expect(screen.getByRole("button", { name: "네, 맞아요" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "직접 고칠게요" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "문서에서 확인하기 어려워요" })).toBeEnabled();
    expect(screen.queryByRole("textbox", { name: "보증금 수정 내용" })).not.toBeInTheDocument();
  });

  it("편집과 확인 불가 DOM에 내부 key를 노출하지 않는다", () => {
    const { container } = renderCard();

    fireEvent.click(screen.getByRole("button", { name: "직접 고칠게요" }));
    expect(container.innerHTML).not.toContain("contract:deposit");
    fireEvent.click(screen.getByRole("button", { name: "수정 취소" }));
    fireEvent.click(screen.getByRole("button", { name: "문서에서 확인하기 어려워요" }));
    expect(container.innerHTML).not.toContain("contract:deposit");
  });

  it("확인 불가 이유를 고르면 정확한 enum을 한 번 전달한다", () => {
    const { onCannotVerify } = renderCard();

    fireEvent.click(screen.getByRole("button", { name: "문서에서 확인하기 어려워요" }));

    expect(screen.getByLabelText("문서에 적혀 있지 않아요")).toBeInTheDocument();
    expect(screen.getByLabelText("글자가 흐려서 확인하기 어려워요")).toBeInTheDocument();
    expect(screen.getByLabelText("어디를 봐야 할지 모르겠어요")).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText("글자가 흐려서 확인하기 어려워요"));
    expect(onCannotVerify).toHaveBeenCalledTimes(1);
    expect(onCannotVerify).toHaveBeenCalledWith("unreadable");
  });

  it("수정은 저장할 때만 전달하고 빈 값은 안내한다", () => {
    const { onChange } = renderCard();

    fireEvent.click(screen.getByRole("button", { name: "직접 고칠게요" }));
    const input = screen.getByRole("textbox", { name: "보증금 수정 내용" });
    expect(input).toHaveValue("10,000,000");
    fireEvent.change(input, { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: "수정한 내용 사용하기" }));
    expect(screen.getByRole("alert")).toHaveTextContent("수정할 내용을 입력해 주세요.");
    expect(onChange).not.toHaveBeenCalled();

    fireEvent.change(input, { target: { value: "12,000,000" } });
    fireEvent.click(screen.getByRole("button", { name: "수정한 내용 사용하기" }));
    expect(onChange).toHaveBeenCalledWith("12,000,000");
  });

  it("특약 수정은 한 textarea에서 줄바꿈 기준 배열로 전달하고 취소는 전달하지 않는다", () => {
    const { onChange } = renderCard({
      item: item("special_clauses", "반려동물 금지, 금연"),
      draftValue: ["반려동물 금지", "금연"],
    });

    fireEvent.click(screen.getByRole("button", { name: "직접 고칠게요" }));
    const textarea = screen.getByRole("textbox", { name: "특약사항 수정 내용" });
    expect(textarea).toHaveValue("반려동물 금지\n금연");
    fireEvent.click(screen.getByRole("button", { name: "수정 취소" }));
    expect(onChange).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "직접 고칠게요" }));
    fireEvent.change(screen.getByRole("textbox", { name: "특약사항 수정 내용" }), {
      target: { value: "반려동물 금지\n금연\n주차 가능" },
    });
    fireEvent.click(screen.getByRole("button", { name: "수정한 내용 사용하기" }));
    expect(onChange).toHaveBeenCalledWith(["반려동물 금지", "금연", "주차 가능"]);
  });

  it("busy이면 모든 행동과 확인 불가 이유 선택을 막는다", () => {
    renderCard({ busy: true });

    expect(screen.getByRole("button", { name: "네, 맞아요" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "직접 고칠게요" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "문서에서 확인하기 어려워요" })).toBeDisabled();
  });

  it("item이 바뀌면 편집 상태와 오류를 지우고 새 현재값으로 초기화한다", () => {
    const card = renderCard();

    fireEvent.click(screen.getByRole("button", { name: "직접 고칠게요" }));
    fireEvent.change(screen.getByRole("textbox", { name: "보증금 수정 내용" }), {
      target: { value: "" },
    });
    fireEvent.click(screen.getByRole("button", { name: "수정한 내용 사용하기" }));
    expect(screen.getByRole("alert")).toBeInTheDocument();

    const nextItem = item("monthly_rent", "500,000");
    card.rerender(
      <GuidedReviewCard
        item={nextItem}
        draftValue="550,000"
        busy={false}
        onConfirm={card.onConfirm}
        onChange={card.onChange}
        onCannotVerify={card.onCannotVerify}
      />,
    );

    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "네, 맞아요" })).toBeEnabled();
    fireEvent.click(screen.getByRole("button", { name: "직접 고칠게요" }));
    expect(screen.getByRole("textbox", { name: "보증금 수정 내용" })).toHaveValue("550,000");
  });

  it("item이 바뀌면 확인 불가 상태를 기본 보기로 되돌린다", () => {
    const card = renderCard();

    fireEvent.click(screen.getByRole("button", { name: "문서에서 확인하기 어려워요" }));
    expect(screen.getByRole("group", { name: "확인하기 어려운 이유" })).toBeInTheDocument();

    card.rerender(
      <GuidedReviewCard
        item={item("monthly_rent", "500,000")}
        draftValue={undefined}
        busy={false}
        onConfirm={card.onConfirm}
        onChange={card.onChange}
        onCannotVerify={card.onCannotVerify}
      />,
    );

    expect(screen.queryByRole("group", { name: "확인하기 어려운 이유" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "네, 맞아요" })).toBeEnabled();
  });

  it("busy로 바뀌면 편집 입력과 저장·취소를 모두 막는다", () => {
    const card = renderCard();
    fireEvent.click(screen.getByRole("button", { name: "직접 고칠게요" }));

    card.rerender(
      <GuidedReviewCard
        item={card.item}
        draftValue={card.draftValue}
        busy
        onConfirm={card.onConfirm}
        onChange={card.onChange}
        onCannotVerify={card.onCannotVerify}
      />,
    );

    expect(screen.getByRole("textbox", { name: "보증금 수정 내용" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "수정한 내용 사용하기" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "수정 취소" })).toBeDisabled();
  });

  it("busy로 바뀌면 확인 불가 이유 라디오를 모두 막는다", () => {
    const card = renderCard();
    fireEvent.click(screen.getByRole("button", { name: "문서에서 확인하기 어려워요" }));

    card.rerender(
      <GuidedReviewCard
        item={card.item}
        draftValue={card.draftValue}
        busy
        onConfirm={card.onConfirm}
        onChange={card.onChange}
        onCannotVerify={card.onCannotVerify}
      />,
    );

    expect(screen.getByLabelText("문서에 적혀 있지 않아요")).toBeDisabled();
    expect(screen.getByLabelText("글자가 흐려서 확인하기 어려워요")).toBeDisabled();
    expect(screen.getByLabelText("어디를 봐야 할지 모르겠어요")).toBeDisabled();
  });
});

afterEach(cleanup);
