import { expect, test, type Page, type TestInfo } from "@playwright/test";

type PracticeScenario = {
  id: string;
  slug: string;
  title: string;
  clause: string;
  answers: [string, string, string];
  confirmedActions: [string, string, string];
  officialSourceNames: string[];
};

const scenarios: PracticeScenario[] = [
  {
    id: "PRACTICE-DEFERRED-REFUND-001",
    slug: "refund",
    title: "후임 임차인 조건부 보증금 반환",
    clause: "보증금은 신규 임차인이 입주한 후 반환한다.",
    answers: [
      "임대차 종료일과 관계없이 신규 임차인이 입주해야만 반환한다는 뜻인지 확인해 주세요.",
      "구두 약속이 아니라 신규 임차인 입주와 관계없이 계약 종료 시 반환하도록 특약을 수정해 주세요.",
      "신규 임차인 조건을 삭제한 특약 문구를 확인하기 전에는 계약을 진행하지 않겠습니다.",
    ],
    confirmedActions: [
      "후임 임차인 조건부 반환 구조 확인",
      "구두 설명 대신 반환 특약 수정 요구",
      "특약 수정 확인 전 계약 진행 보류",
    ],
    officialSourceNames: ["주택임대차보호법", "주택임대차 표준계약서"],
  },
  {
    id: "PRACTICE-THIRD-PARTY-PAYMENT-001",
    slug: "payee",
    title: "공인중개사 명의 계좌로 가계약금 송금 요구",
    clause: "계약 후 잔금 지급일까지 임차인의 권리를 해치는 새로운 권리를 설정하지 않는다.",
    answers: [
      "입금 명의가 중개사님이고 임대인과 등기상 소유자 박서연 씨가 아닌 이유부터 확인하겠습니다.",
      "임대인과 어떤 관계인지, 가계약금을 대신 받을 권한을 증명하는 자료가 있는지 확인하겠습니다.",
      "입금 명의와 가계약금 수령 권한을 확인하기 전에는 송금하지 않겠습니다.",
    ],
    confirmedActions: [
      "입금 명의와 계약 상대 불일치 확인",
      "제3자 수령 관계와 권한 자료 확인",
      "확인 완료 전 가계약금 송금 보류",
    ],
    officialSourceNames: ["주택임대차 표준계약서", "안심 전세계약 체크리스트"],
  },
  {
    id: "PRACTICE-PROXY-AUTHORITY-001",
    slug: "proxy",
    title: "대리인 권한 자료 없는 계약 요구",
    clause: "계약 체결은 임대인의 대리인이 진행한다.",
    answers: [
      "등기상 소유자가 한서윤 씨인지 확인하고 박민준 씨가 어떤 관계로 계약하는지도 확인하겠습니다.",
      "계약 전에 위임장과 인감증명서를 보고 계약 체결과 계약금 수령 권한까지 확인하겠습니다.",
      "대리인의 계약 체결 권한과 계약금 수령 권한을 확인하기 전에는 서명도 송금도 하지 않겠습니다.",
    ],
    confirmedActions: [
      "등기상 소유자와 계약 상대 확인",
      "대리인 권한 서류와 권한 범위 확인",
      "권한 확인 전 서명·송금 보류",
    ],
    officialSourceNames: ["안심 전세계약 체크리스트", "주택임대차 표준계약서"],
  },
];

async function signUpAndOpenPractice(page: Page, scenario: PracticeScenario, testInfo: TestInfo) {
  const viewport = page.viewportSize()?.width ?? 0;
  const projectSlug = viewport >= 1024 ? "desktop" : `mobile${viewport}`;
  const username = `practice_${scenario.slug}_${projectSlug}_${Date.now().toString(36)}`;

  await page.goto("/signup");
  await page.getByLabel("아이디").fill(username);
  await page.getByLabel("이메일").fill(`${username}@example.com`);
  await page.getByLabel("비밀번호").fill("password1!");
  await page.getByRole("button", { name: "회원가입" }).click();
  await expect(page).toHaveURL(/\/login$/);

  await page.getByLabel("아이디").fill(username);
  await page.getByLabel("비밀번호").fill("password1!");
  await page.getByRole("button", { name: "로그인하고 시작" }).click();
  await expect(page.getByRole("heading", { name: "어떤 방식으로 시작할까요?" })).toBeVisible();
  await page.getByRole("link", { name: "연습 시뮬레이션 시작" }).click();
  await expect(page.getByRole("heading", { name: "계약 대화 연습" })).toBeVisible();

  const catalog = page.getByRole("region", { name: "연습 시나리오 목록" });
  await expect(catalog.locator("article")).toHaveCount(3);
  for (const availableScenario of scenarios) {
    await expect(catalog.getByRole("heading", { name: availableScenario.title })).toBeVisible();
  }

  if (scenario === scenarios[0]) {
    const cards = catalog.locator("article");
    const first = await cards.nth(0).boundingBox();
    const second = await cards.nth(1).boundingBox();
    expect(first).not.toBeNull();
    expect(second).not.toBeNull();
    if (viewport >= 1024) {
      expect((second?.x ?? 0) > (first?.x ?? 0)).toBeTruthy();
    } else {
      expect((second?.y ?? 0) > (first?.y ?? 0)).toBeTruthy();
    }
  }

  const card = catalog.locator("article").filter({ has: page.getByRole("heading", { name: scenario.title }) });
  await card.getByRole("link", { name: "상황 먼저 보기" }).click();
  await expect(page).toHaveURL(new RegExp(`/practice/scenarios/${scenario.id}$`));
  await expect(page.getByRole("heading", { name: "주택임대차계약서 확인" })).toBeVisible();
  await expect(page.getByRole("region", { name: "주택임대차계약서" })).toContainText(scenario.clause);
  await expect(page.getByRole("heading", { name: scenario.title })).toHaveCount(0);
  await expect(page.getByText("가상 연습", { exact: true })).toHaveCount(0);
  await expect(page.getByText("합성 시나리오", { exact: true })).toHaveCount(0);

  if (testInfo.project.name.startsWith("real-api")) {
    await expect(page.getByRole("button", { name: "계약서 확인 완료 · 대화 시작" })).toBeEnabled();
  }
}

async function submitAnswer(page: Page, answer: string, expectedTurn: string) {
  await expect(page.getByLabel("내 답변")).toBeVisible();
  await page.getByLabel("내 답변").fill(answer);
  await page.getByRole("button", { name: "답변 보내기" }).click();
  await expect(page.getByRole("status", { name: "연습 진행 상태" })).toContainText(expectedTurn);
}

test.describe("세 가지 계약 대화 연습", () => {
  for (const scenario of scenarios) {
    test(`${scenario.title}: 시작부터 저장된 복기까지 완료한다`, async ({ page }, testInfo) => {
      await signUpAndOpenPractice(page, scenario, testInfo);
      await page.getByRole("button", { name: "계약서 확인 완료 · 대화 시작" }).click();
      await expect(page).toHaveURL(/\/practice\/sessions\/[^/]+$/);
      await expect(page.getByRole("status", { name: "연습 진행 상태" })).toContainText("TURN-01");
      await expect(page.locator("video[src='/practice/avatar/speaking.mp4']")).toBeVisible();

      await page.getByRole("button", { name: "답변하지 못했어요" }).click();
      await expect(page.getByText("답변을 기다리고 있습니다. 같은 상황에서 다시 말해 보세요.")).toBeVisible();
      await expect(page.getByRole("status", { name: "연습 진행 상태" })).toContainText("TURN-01");

      await submitAnswer(page, scenario.answers[0], "TURN-02");
      await expect(page.getByRole("status", { name: "연습 진행 상태" })).toContainText("확인한 행동 1개");

      await page.reload();
      await expect(page.getByRole("status", { name: "연습 진행 상태" })).toContainText("TURN-02");
      await expect(page.getByRole("status", { name: "연습 진행 상태" })).toContainText("확인한 행동 1개");

      await submitAnswer(page, scenario.answers[1], "TURN-03");
      await submitAnswer(page, scenario.answers[2], "최종 행동 선택");
      await expect(page.getByRole("heading", { name: "이 계약 상황에서 어떻게 행동하시겠습니까?" })).toBeVisible();
      await page.getByRole("button", { name: "보류", exact: true }).click();

      await expect(page).toHaveURL(/\/practice\/sessions\/[^/]+\/result$/);
      await expect(page.getByRole("heading", { name: "연습 결과 복기" })).toBeVisible();
      await expect(page.getByRole("heading", { name: "보류", exact: true })).toBeVisible();
      const confirmed = page.getByRole("heading", { name: "잘 확인한 행동" }).locator("xpath=parent::section");
      for (const action of scenario.confirmedActions) await expect(confirmed).toContainText(action);
      await expect(page.getByText("이번 연습에서 놓친 확인 신호가 없습니다.")).toBeVisible();
      const sources = page.getByRole("heading", { name: "연결된 공식 근거" }).locator("xpath=parent::section");
      for (const sourceName of scenario.officialSourceNames) await expect(sources).toContainText(sourceName);

      await page.reload();
      await expect(page.getByRole("heading", { name: "연습 결과 복기" })).toBeVisible();
      await expect(page.getByRole("heading", { name: "보류", exact: true })).toBeVisible();
      await expect(page.getByRole("link", { name: "같은 상황 다시 연습" })).toHaveAttribute(
        "href",
        `/practice/scenarios/${scenario.id}`,
      );
    });
  }
});
