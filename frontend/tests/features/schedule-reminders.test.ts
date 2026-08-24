import { describe, expect, it } from "vitest";
import {
  buildScheduleReminders,
  ddayLabel,
  daysUntil,
} from "../../src/features/schedule-reminders/reminders";

const today = new Date(2026, 7, 24); // 2026-08-24 로컬 자정

describe("일정 알림", () => {
  it("잔금일·입주일에서 D-day를 계산하고 급한 순으로 정렬한다", () => {
    const reminders = buildScheduleReminders(
      {
        balancePaymentDate: "2026-08-20", // 지남
        moveInDate: "2026-08-26", // D-2
        pendingChecklistCount: 3,
        pendingPostActionCount: 0,
      },
      today,
    );

    expect(reminders.map((item) => item.id)).toEqual([
      "balance-registry-recheck",
      "move-in-rights",
      "pending-checklist",
    ]);
    expect(reminders[0].tone).toBe("passed");
    expect(reminders[1].daysLeft).toBe(2);
    expect(reminders[1].tone).toBe("soon");
    expect(reminders[2].title).toContain("3개");
  });

  it("날짜가 없으면 날짜 기반 알림을 만들지 않는다", () => {
    const reminders = buildScheduleReminders(
      {
        balancePaymentDate: null,
        moveInDate: null,
        pendingChecklistCount: 0,
        pendingPostActionCount: 0,
      },
      today,
    );
    expect(reminders).toEqual([]);
  });

  it("D-day 표기는 오늘·남음·지남을 구분한다", () => {
    expect(daysUntil("2026-08-24", today)).toBe(0);
    expect(ddayLabel(0)).toBe("오늘");
    expect(ddayLabel(5)).toBe("D-5");
    expect(ddayLabel(-2)).toBe("2일 지남");
    expect(ddayLabel(null)).toBe("날짜 미입력");
  });
});
