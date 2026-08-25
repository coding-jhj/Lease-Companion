/**
 * 계약 일정 알림 — 저장된 잔금일·입주일과 남은 확인 항목으로 "지금 챙길 일"을 만든다.
 *
 * 새 판정을 만들지 않는다. 날짜는 사용자가 입력한 값 그대로 쓰고, 문구는 공식 자료
 * (국토교통부 체크리스트·주택임대차보호법)에 있는 절차만 안내한다.
 */

export type ReminderTone = "due" | "soon" | "later" | "passed";

export interface ScheduleReminder {
  id: string;
  title: string;
  /** 기준 날짜 (YYYY-MM-DD). 날짜가 없는 알림은 null. */
  date: string | null;
  /** 기준일까지 남은 일수. 지났으면 음수, 날짜가 없으면 null. */
  daysLeft: number | null;
  tone: ReminderTone;
  detail: string;
}

export interface ReminderInput {
  balancePaymentDate: string | null;
  moveInDate: string | null;
  pendingChecklistCount: number;
  pendingPostActionCount: number;
}

const DAY_MS = 24 * 60 * 60 * 1000;

/** 로컬 자정 기준 일수 차이. 시각 차이 때문에 D-day가 하루씩 밀리지 않게 한다. */
export function daysUntil(date: string, today: Date): number | null {
  const target = new Date(`${date}T00:00:00`);
  if (Number.isNaN(target.getTime())) return null;
  const base = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  return Math.round((target.getTime() - base.getTime()) / DAY_MS);
}

function toneFor(daysLeft: number | null): ReminderTone {
  if (daysLeft === null) return "later";
  if (daysLeft < 0) return "passed";
  if (daysLeft === 0) return "due";
  if (daysLeft <= 3) return "soon";
  return "later";
}

export function ddayLabel(daysLeft: number | null): string {
  if (daysLeft === null) return "날짜 미입력";
  if (daysLeft === 0) return "오늘";
  if (daysLeft > 0) return `D-${daysLeft}`;
  return `${-daysLeft}일 지남`;
}

export function buildScheduleReminders(
  input: ReminderInput,
  today: Date = new Date(),
): ScheduleReminder[] {
  const reminders: ScheduleReminder[] = [];

  if (input.balancePaymentDate) {
    const daysLeft = daysUntil(input.balancePaymentDate, today);
    reminders.push({
      id: "balance-registry-recheck",
      title: "잔금 보내기 전에 등기사항증명서를 다시 확인하세요",
      date: input.balancePaymentDate,
      daysLeft,
      tone: toneFor(daysLeft),
      detail: "송금 직전에 새 등기사항증명서를 발급해 소유자와 근저당·압류 변동을 계약 때 자료와 대조하세요.",
    });
  }

  if (input.moveInDate) {
    const daysLeft = daysUntil(input.moveInDate, today);
    reminders.push({
      id: "move-in-rights",
      title: "입주 후 전입신고와 확정일자를 확인하세요",
      date: input.moveInDate,
      daysLeft,
      tone: toneFor(daysLeft),
      detail: "주택을 인도받고 전입신고를 마치면 그 다음 날부터 대항력이 생깁니다(주택임대차보호법 제3조). 확정일자까지 함께 확인하세요.",
    });
  }

  if (input.pendingChecklistCount > 0) {
    reminders.push({
      id: "pending-checklist",
      title: `서명 전 체크리스트 ${input.pendingChecklistCount}개가 남아 있습니다`,
      date: null,
      daysLeft: null,
      tone: "later",
      detail: "남은 항목을 확인하고 체크해 두면 나중에 무엇을 확인했는지 그대로 남습니다.",
    });
  }

  if (input.pendingPostActionCount > 0) {
    reminders.push({
      id: "pending-post-action",
      title: `계약 후 행동 ${input.pendingPostActionCount}개가 남아 있습니다`,
      date: null,
      daysLeft: null,
      tone: "later",
      detail: "권리 확보 절차는 시기를 놓치면 되돌리기 어렵습니다. 남은 행동을 차례로 확인하세요.",
    });
  }

  // 급한 것부터: 지난 일정 → 오늘 → 임박 → 나머지.
  const order: Record<ReminderTone, number> = { passed: 0, due: 1, soon: 2, later: 3 };
  return reminders.sort((left, right) => order[left.tone] - order[right.tone]);
}
