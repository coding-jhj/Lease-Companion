import { expect, test } from "@playwright/test";

test("critical upload, review, analysis, and report actions work with the keyboard", async ({ page }) => {
  const suffix = Date.now().toString(36);
  const username = `keyboard_${suffix}`;

  await page.goto("/signup");
  await page.getByLabel("아이디").fill(username);
  await page.getByLabel("이메일").fill(`${username}@example.com`);
  await page.getByLabel("비밀번호").fill("password1!");
  await page.getByRole("button", { name: "회원가입" }).click();
  await page.getByLabel("아이디").fill(username);
  await page.getByLabel("비밀번호").fill("password1!");
  await page.getByRole("button", { name: "로그인하고 시작" }).click();
  await page.getByRole("link", { name: "새 계약 만들기" }).click();
  await page.getByLabel("계약 이름").fill("키보드 접근성 계약");
  await page.getByRole("button", { name: "계약 상황 입력하기" }).click();
  await page.getByLabel("대리 계약 여부").selectOption("no");
  await page.getByRole("button", { name: "문서 업로드하기" }).click();

  const contractPicker = page.getByRole("button", { name: "계약서 파일 선택" });
  const registryPicker = page.getByRole("button", { name: "등기사항증명서 파일 선택" });
  await contractPicker.focus();
  await expect(contractPicker).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(registryPicker).toBeFocused();
  await page.keyboard.press("Shift+Tab");
  await expect(contractPicker).toBeFocused();

  await page.getByLabel("계약서", { exact: true }).setInputFiles({
    name: "keyboard-contract.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("synthetic lease contract"),
  });
  const startExtraction = page.getByRole("button", { name: "업로드하고 추출 시작하기" });
  await startExtraction.focus();
  await expect(startExtraction).toBeFocused();
  await page.keyboard.press("Enter");

  const confirmAll = page.getByRole("button", { name: "읽힌 값 모두 확인" });
  await expect(confirmAll).toBeVisible({ timeout: 60_000 });
  await confirmAll.focus();
  await page.keyboard.press("Enter");
  const confirmedFieldsSummary = page.getByText(/확인된 항목 \d+개/).locator("..");
  await confirmedFieldsSummary.focus();
  await expect(confirmedFieldsSummary).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(confirmedFieldsSummary.locator("..")).toHaveAttribute("open", "");
  const clauseSummary = page.getByText(/조항 \d+개 펼쳐서 확인/).first();
  await clauseSummary.focus();
  await expect(clauseSummary).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(clauseSummary.locator("..")).toHaveAttribute("open", "");

  const startAnalysis = page.getByRole("button", { name: "확인 완료하고 분석하기" });
  await startAnalysis.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { name: "계약 분석 진행 상황" })).toBeVisible();
  await expect(page.getByText("리포트 준비 완료").locator("xpath=ancestor::li")).toHaveAttribute("aria-current", "step", { timeout: 60_000 });
  const reportButton = page.getByRole("button", { name: "리포트 보기" });
  await reportButton.focus();
  await page.keyboard.press("Enter");

  const firstPriorityLink = page.getByRole("link", { name: "가장 먼저 확인할 항목으로 이동" });
  await firstPriorityLink.focus();
  await expect(firstPriorityLink).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/#first-priority-group$/);

  const evidenceSummary = page.getByText("근거와 판정 한계 확인").first();
  await evidenceSummary.focus();
  await expect(evidenceSummary).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(evidenceSummary.locator("..")).toHaveAttribute("open", "");

  const checklistButton = page.getByRole("button", { name: "저장된 체크리스트로 이동" });
  await checklistButton.focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { name: "체크리스트와 계약 직후 행동" })).toBeVisible();
});
