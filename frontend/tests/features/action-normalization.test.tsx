import { describe, expect, it } from "vitest";
import { normalizeAction, toPoliteEnding } from "../../src/features/question-cards/actionNormalization";

describe("toPoliteEnding", () => {
  it("converts plain declarative endings to soft polite", () => {
    expect(toPoliteEnding("확인한다.")).toBe("확인하세요.");
    expect(toPoliteEnding("임대인 본인에게 직접 전화하여 위임 사실을 확인한다.")).toBe(
      "임대인 본인에게 직접 전화하여 위임 사실을 확인한다.".replace("확인한다.", "확인하세요."),
    );
    expect(toPoliteEnding("인터넷등기소에서 계약 당일 발급된 등기사항증명서인지 확인한다.")).toMatch(/확인하세요\.$/);
    expect(toPoliteEnding("최신 등기를 발급받는다.")).toBe("최신 등기를 발급받으세요.");
    expect(toPoliteEnding("직접 확인하십시오.")).toBe("직접 확인하세요.");
  });

  it("leaves mid-sentence 한다 forms untouched", () => {
    expect(toPoliteEnding("확인한다면 좋습니다.")).toBe("확인한다면 좋습니다.");
  });

  it("normalizeAction applies polite ending to pass-through text", () => {
    expect(normalizeAction("위임 사실을 확인한다.", "checklist").text).toBe("위임 사실을 확인하세요.");
  });
});
