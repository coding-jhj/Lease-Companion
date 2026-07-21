import { expect, test } from "@playwright/test";

async function expandAllResultGroups(page: import("@playwright/test").Page) {
  for (const label of ["확인 권장", "일반 확인"]) {
    const toggle = page.getByRole("button", { name: new RegExp(`^${label}`) });
    if (await toggle.getAttribute("aria-expanded") === "false") await toggle.click();
  }
  const unavailableToggle = page.getByRole("button", { name: /^지금 판단할 수 없는 항목/ });
  if (await unavailableToggle.count() && await unavailableToggle.getAttribute("aria-expanded") === "false") {
    await unavailableToggle.click();
  }
}

test("v1.9 signup through saved checklist follows the complete MVP flow", async ({ page }, testInfo) => {
  const isRealApi = testInfo.project.name.startsWith("real-api");
  const userSuffix = Date.now().toString(36);
  const username = `e2e_${userSuffix}`;
  await page.goto("/signup");
  await page.getByLabel("아이디").fill(username);
  await page.getByLabel("이메일").fill(`${username}@example.com`);
  await page.getByLabel("비밀번호").fill("password1!");
  await page.getByRole("button", { name: "회원가입" }).click();
  await expect(page).toHaveURL(/\/login$/);

  await page.getByLabel("아이디").fill(username);
  await page.getByLabel("비밀번호").fill("password1!");
  await page.getByRole("button", { name: "로그인하고 시작" }).click();
  await expect(page.getByRole("heading", { name: "내 계약" })).toBeVisible();
  if ((page.viewportSize()?.width ?? 0) >= 1024) {
    await expect(page.locator("main.app-shell")).toHaveClass(/app-shell--workspace/);
    await expect.poll(async () => (await page.locator("main.app-shell").boundingBox())?.width ?? 0).toBeGreaterThan(1000);
  }

  await page.getByRole("link", { name: "새 계약 만들기" }).click();
  await page.getByLabel("계약 이름").fill("E2E 전세 계약");
  await page.getByRole("button", { name: "계약 상황 입력하기" }).click();
  await page.getByLabel("대리 계약 여부").selectOption("no");
  await page.getByRole("button", { name: "문서 업로드하기" }).click();

  await page.getByLabel("계약서", { exact: true }).setInputFiles({
    name: "contract.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("synthetic lease contract"),
  });
  await expect(page.getByText("contract.txt")).toBeVisible();
  await page.getByRole("button", { name: "업로드하고 추출 시작하기" }).click();

  await expect(page.getByRole("heading", { name: "추출값 확인·수정" })).toBeVisible();
  await expect(page.getByRole("button", { name: "읽힌 값 모두 확인" })).toBeVisible({ timeout: 60_000 });
  if (isRealApi) {
    await expect.poll(() => page.locator(".field-card").count()).toBeGreaterThan(0);
  } else {
    await expect(page.getByLabel("보증금 반환 조항 원문 값")).toBeVisible();
    await expect(page.getByLabel("수리·원상복구 조항 원문 값")).toBeVisible();
    await expect(page.getByLabel("보증금 반환 조건 값")).toHaveCount(0);
    await expect(page.getByLabel("수리·원상복구 책임 값")).toHaveCount(0);
  }
  await page.getByRole("button", { name: "읽힌 값 모두 확인" }).click();
  const confirmedFields = page.getByText(/확인된 항목 \d+개/);
  if (await confirmedFields.count()) await confirmedFields.click();
  const accountHolder = page.getByLabel("입금 계좌 예금주 값");
  if (await accountHolder.count()) {
    await accountHolder.fill("이정훈");
    await page.getByRole("button", { name: "입금 계좌 예금주 이 값 확인" }).click();
  }
  const secondMainClause = page.getByLabel("계약서 본문 주요 조항 2 값");
  if (await secondMainClause.count()) {
    await page.getByText(/조항 \d+개 펼쳐서 확인/).first().click();
    await secondMainClause.fill("주요 설비 하자 수선은 임대인이 부담하고, 임차인에게 알린다.");
    await page.getByRole("button", { name: "계약서 본문 주요 조항 이 값 확인" }).click();
  }
  await page.getByRole("button", { name: "확인 완료하고 분석하기" }).click();

  await expect(page.getByRole("heading", { name: "분석 완료" })).toBeVisible({ timeout: 60_000 });
  await page.getByRole("button", { name: "리포트 보기" }).click();
  await expect(page.getByRole("heading", { name: "방어 행동 허브" })).toBeVisible();
  if ((page.viewportSize()?.width ?? 0) >= 1024) {
    await expect(page.locator("main.app-shell")).toHaveClass(/app-shell--report/);
    const resultsBox = await page.locator(".report-results-column").boundingBox();
    const guidanceBox = await page.locator(".report-guidance-column").boundingBox();
    expect(resultsBox).not.toBeNull();
    expect(guidanceBox).not.toBeNull();
    expect((guidanceBox?.x ?? 0) > (resultsBox?.x ?? 0)).toBeTruthy();
  }
  const allResults = page.locator('section[aria-labelledby="all-results-title"]');
  await expandAllResultGroups(page);
  for (const judgmentId of Array.from({ length: 12 }, (_, index) => `J${String(index + 1).padStart(2, "0")}`)) {
    await expect(allResults).toContainText(judgmentId);
  }
  await expect(allResults).not.toContainText("R01");
  await expect(allResults).toContainText("상태:");
  for (const title of ["먼저 물어볼 질문", "수정·추가 요청 문구", "계약 전", "계약 중", "잔금·입주 당일", "계약 후", "보관할 자료"]) {
    await expect(page.getByRole("heading", { name: title })).toBeVisible();
  }
  await expect(page.getByRole("heading", { name: "주요 금전피해 유형 비교" })).toBeVisible();
  await expect(page.getByRole("button", { name: "전체 리포트 PDF 저장" })).toBeVisible();
  await expect(page.getByRole("link", { name: "가장 먼저 확인할 항목으로 이동" })).toBeVisible();

  await page.reload();
  await expect(page.getByRole("heading", { name: "방어 행동 허브" })).toBeVisible();
  await expandAllResultGroups(page);
  await expect(allResults).toContainText("J01");
  await expect(allResults).toContainText("J12");
  await expect(allResults).not.toContainText("R01");

  if (!isRealApi) {
    await page.getByLabel("평점").selectOption("5");
    await page.getByRole("textbox", { name: "의견", exact: true }).fill("전체 흐름 확인 완료");
    await page.getByRole("button", { name: "의견 저장" }).click();
    await expect(page.getByRole("status")).toContainText("의견이 저장되었습니다.");
  }

  await page.getByRole("button", { name: "저장된 체크리스트로 이동" }).click();
  const checklistSection = page.locator("section.history-section").filter({
    has: page.getByRole("heading", { name: "서명 전 체크리스트" }),
  });
  const action = checklistSection.locator("button.check-item__button").first();
  await expect(action).toBeVisible();
  if ((await action.getAttribute("aria-label"))?.endsWith(" 확인")) await action.click();
  const completedChecklistSection = page.locator("section.history-section").filter({
    has: page.getByRole("heading", { name: "완료된 체크리스트 항목" }),
  });
  const completedAction = completedChecklistSection.locator("button.check-item__button").first();
  await expect(completedAction).toHaveAttribute("aria-label", /확인 취소$/);
  const analysisHistory = page.locator("section.history-section").filter({
    has: page.getByRole("heading", { name: "분석 이력" }),
  });
  await expect(analysisHistory).toContainText("완료 리포트 보기");

  if (isRealApi) {
    await page.reload();
    await expect(completedAction).toHaveAttribute("aria-label", /확인 취소$/);
    await expect(analysisHistory).toContainText("완료 리포트 보기");
  }
});
