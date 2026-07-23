import { expect, test, type Page, type TestInfo } from "@playwright/test";

type PracticeScenario = {
  id: string;
  slug: string;
  title: string;
  clause: string;
  nextPrompt: string;
  answers: [string, string, string];
  confirmedActions: [string, string, string];
  officialSourceNames: string[];
};

const scenarios: PracticeScenario[] = [
  {
    id: "PRACTICE-DEFERRED-REFUND-001",
    slug: "refund",
    title: "후임 임차인 조건부 보증금 반환",
    clause: "임대인은 신규 임차인의 입주 및 보증금 수령이 완료된 후 임차인에게 임대차보증금을 반환한다.",
    nextPrompt: "임대인분 말씀으로는 새 세입자는 금방 구해질 테니 걱정하지 않으셔도 된다고 합니다. 구두로도 확실히 약속하셨습니다.",
    answers: [
      "임대차 종료일과 관계없이 신규 임차인이 입주해야만 반환한다는 뜻인지 확인해 주세요.",
      "구두 약속이 아니라 신규 임차인 입주와 관계없이 계약 종료 시 반환하도록 특약을 수정해 주세요.",
      "신규 임차인 조건을 삭제한 특약 문구를 확인하기 전에는 계약을 진행하지 않겠습니다.",
    ],
    confirmedActions: ["후임 임차인 조건부 반환 구조 확인", "구두 설명 대신 반환 특약 수정 요구", "특약 수정 확인 전 계약 진행 보류"],
    officialSourceNames: ["주택임대차보호법", "주택임대차 표준계약서"],
  },
  {
    id: "PRACTICE-THIRD-PARTY-PAYMENT-001",
    slug: "payee",
    title: "공인중개사 명의 계좌로 가계약금 송금 요구",
    clause: "계약금 및 잔금은 임대인이 지정한 계좌로 지급하고, 임대인은 지급받은 금액에 대한 영수증을 교부한다.",
    nextPrompt: "중개사 계좌로 받는 경우도 많고 제가 영수증을 드리면 됩니다. 별도 서류까지 필요할까요?",
    answers: [
      "입금 명의가 중개사님이고 임대인과 등기상 소유자 박서연 씨가 아닌 이유부터 확인하겠습니다.",
      "임대인과 어떤 관계인지, 가계약금을 대신 받을 권한을 증명하는 자료가 있는지 확인하겠습니다.",
      "입금 명의와 가계약금 수령 권한을 확인하기 전에는 송금하지 않겠습니다.",
    ],
    confirmedActions: ["입금 명의와 계약 상대 불일치 확인", "제3자 수령 관계와 권한 자료 확인", "확인 완료 전 가계약금 송금 보류"],
    officialSourceNames: ["주택임대차 표준계약서", "안심 전세계약 체크리스트"],
  },
  {
    id: "PRACTICE-PROXY-AUTHORITY-001",
    slug: "proxy",
    title: "대리인 권한 자료 없는 계약 요구",
    clause: "본 계약의 체결 및 계약금 수령에 관한 절차는 임대인이 지정한 대리인 박민준을 통하여 진행한다.",
    nextPrompt: "위임장과 인감증명서는 계약 후에 보내드릴 수 있습니다. 대리인 신분증만 확인하고 서명하시죠.",
    answers: [
      "등기상 소유자가 한서윤 씨인지 확인하고 박민준 씨가 어떤 관계로 계약하는지도 확인하겠습니다.",
      "계약 전에 위임장과 인감증명서를 보고 계약 체결과 계약금 수령 권한까지 확인하겠습니다.",
      "대리인의 계약 체결 권한과 계약금 수령 권한을 확인하기 전에는 서명도 송금도 하지 않겠습니다.",
    ],
    confirmedActions: ["등기상 소유자와 계약 상대 확인", "대리인 권한 서류와 권한 범위 확인", "권한 확인 전 서명·송금 보류"],
    officialSourceNames: ["안심 전세계약 체크리스트", "주택임대차 표준계약서"],
  },
];

async function signUpAndOpenPractice(page: Page, scenario: PracticeScenario, testInfo: TestInfo) {
  const viewport = page.viewportSize()?.width ?? 0;
  const username = `practice_${scenario.slug}_${viewport}_${Date.now().toString(36)}`;
  await page.goto("/signup");
  await page.getByLabel("아이디").fill(username);
  await page.getByLabel("이메일").fill(`${username}@example.com`);
  await page.getByLabel("비밀번호").fill("password1!");
  await page.getByRole("button", { name: "회원가입" }).click();
  await page.getByLabel("아이디").fill(username);
  await page.getByLabel("비밀번호").fill("password1!");
  await page.getByRole("button", { name: "로그인하고 시작" }).click();
  await page.getByRole("link", { name: "아직 계약서를 받지 않았어요" }).click();
  await page.getByRole("link", { name: "이 상황을 연습해 볼게요" }).click();
  await expect(page.getByRole("heading", { name: "계약 상황을 미리 연습해 보세요" })).toBeVisible();

  const catalog = page.getByRole("region", { name: "연습 시나리오 목록" });
  await expect(catalog.locator("article")).toHaveCount(3);
  const card = catalog.locator("article").filter({ has: page.getByRole("heading", { name: scenario.title }) });
  await card.getByRole("link", { name: "상황 확인하기" }).click();
  await expect(page).toHaveURL(new RegExp(`/practice/scenarios/${scenario.id}$`));
  await expect(page.getByRole("heading", { name: "이런 상황입니다" })).toBeVisible();
  await expect(page.getByText(scenario.title, { exact: true })).toBeVisible();
  const contractDetails = page.getByText("참고할 계약 내용 보기").locator("..");
  await expect(contractDetails).not.toHaveAttribute("open", "");
  await contractDetails.click();
  await expect(contractDetails).toContainText(scenario.clause);
  await expect(page.locator("body")).not.toContainText(/가상 연습|합성 시나리오|TURN-|hidden_confirmation_signals|answer key/i);

  if (testInfo.project.name.startsWith("real-api")) {
    await expect(page.getByRole("button", { name: "연습 시작하기" })).toBeEnabled();
  }
}

async function submitAnswer(page: Page, answer: string, staysOnComposer = true) {
  const answerBox = page.getByLabel("내 답변");
  await expect(answerBox).toBeVisible();
  await answerBox.fill(answer);
  await page.getByRole("button", { name: "이렇게 말할게요" }).click();
  if (staysOnComposer) await expect(answerBox).toHaveValue("");
}

async function finishPractice(page: Page, scenario: PracticeScenario) {
  await submitAnswer(page, scenario.answers[0]);
  await submitAnswer(page, scenario.answers[1]);
  await submitAnswer(page, scenario.answers[2], false);
  const finalSection = page.getByRole("heading", { name: "연습 결과 확인하기" }).locator("xpath=ancestor::section[1]");
  await expect(finalSection).toBeVisible();
  await page.getByRole("button", { name: "보류", exact: true }).click();
  await expect(page.locator("button.primary")).toHaveCount(1);
  await finalSection.getByRole("button", { name: "연습 결과 확인하기" }).click();
  await expect(page).toHaveURL(/\/practice\/sessions\/[^/]+\/result$/);
}

async function expectMobilePracticeLayout(page: Page) {
  if ((page.viewportSize()?.width ?? 0) > 360) return;

  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
  const targets = page.locator(".text-link:visible, .app-header a:visible, .app-header button:visible, .practice-avatar-stage__retry:visible, .practice-contract-reference > summary:visible");
  await expect(targets).not.toHaveCount(0);
  for (let index = 0; index < await targets.count(); index += 1) {
    const box = await targets.nth(index).boundingBox();
    expect(box?.height ?? 0, `모바일 상호작용 대상 ${index + 1}의 높이`).toBeGreaterThanOrEqual(44);
  }
  for (const target of [
    page.getByRole("button", { name: "장면 다시 보기" }),
    page.locator("summary").filter({ hasText: "계약 내용 참고하기" }),
  ]) {
    await expect(target).toBeVisible();
    const box = await target.boundingBox();
    expect(box?.height ?? 0, "모바일 연습 핵심 대상의 높이").toBeGreaterThanOrEqual(44);
  }
}

test.describe("세 가지 계약 대화 연습", () => {
  for (const scenario of scenarios) {
    test(`${scenario.title}: 현재 대사만 보이며 결과까지 이동한다`, async ({ page }, testInfo) => {
      await signUpAndOpenPractice(page, scenario, testInfo);
      await page.getByRole("button", { name: "연습 시작하기" }).click();
      await expect(page).toHaveURL(/\/practice\/sessions\/[^/]+$/);
      await expect(page.getByText("미션 진행")).toBeVisible();
      await expect(page.getByTestId("practice-video")).toBeVisible();
      await expect(page.locator("button.primary")).toHaveCount(1);
      await expect(page.locator("body")).not.toContainText(scenario.nextPrompt);
      await expect(page.locator("body")).not.toContainText(/TURN-|hidden_confirmation_signals|answer key/i);
      await expectMobilePracticeLayout(page);

      await page.getByRole("button", { name: "말할 내용 힌트 보기" }).click();
      const hint = page.getByRole("region", { name: "말할 내용 힌트" });
      await expect(hint).toContainText("방향");
      await expect(hint).not.toContainText(/TURN-|hidden_confirmation_signals|answer key/i);
      await page.getByRole("button", { name: "다음 힌트" }).click();
      await expect(hint).toContainText(await page.locator("#practice-avatar-title").textContent() ?? "");

      await finishPractice(page, scenario);
      await expect(page.getByRole("heading", { name: "연습 결과 복기" })).toBeVisible();
      const confirmed = page.getByRole("heading", { name: "잘 확인한 행동" }).locator("xpath=parent::section");
      for (const action of scenario.confirmedActions) await expect(confirmed).toContainText(action);
      const sources = page.getByRole("heading", { name: "연결된 공식 근거" }).locator("xpath=parent::section");
      for (const sourceName of scenario.officialSourceNames) await expect(sources).toContainText(sourceName);
    });
  }

  test("실제 누락 영상 요청에도 현재 대사와 답변 흐름을 유지한다", async ({ page }, testInfo) => {
    const scenario = scenarios[0];
    await signUpAndOpenPractice(page, scenario, testInfo);
    await page.getByRole("button", { name: "연습 시작하기" }).click();
    const video = page.getByTestId("practice-video");
    await expect(video).toBeVisible();
    const missingMediaPath = `/e2e-missing-media-${Date.now()}.mp4`;
    const missingMediaRequest = page.waitForRequest((request) =>
      new URL(request.url()).pathname === missingMediaPath,
    );
    const nativeMediaError = video.evaluate((element) => new Promise<void>((resolve) => {
      element.addEventListener("error", () => resolve(), { once: true });
    }));
    await video.evaluate((element, source) => {
      element.src = source;
      element.load();
    }, missingMediaPath);
    expect(new URL((await missingMediaRequest).url()).pathname).toBe(missingMediaPath);
    await nativeMediaError;

    await expect(page.getByText("영상을 재생하지 못했습니다. 아래 대사로 연습을 계속할 수 있습니다.")).toBeVisible();
    await expect(page.locator(".practice-avatar-stage h2")).toBeVisible();
    await expect(page.getByLabel("내 답변")).toBeVisible();
    await expect(page.locator("button.primary")).toHaveCount(1);
    await expectMobilePracticeLayout(page);
    await finishPractice(page, scenario);
  });
});
