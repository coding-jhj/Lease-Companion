import { expect, test } from "@playwright/test";
import { syntheticLeasePdfFixture } from "./fixtures/syntheticLeasePdf";

test("situation entry and critical report actions work with the keyboard", async ({ page }) => {
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
  await page.getByRole("link", { name: /실전 계약 점검/ }).click();
  const noDraftCard = page.getByRole("link", { name: /아직 계약서를 받지 않았어요/ });
  const draftCard = page.getByRole("link", { name: /계약서 초안을 받았어요/ });
  await noDraftCard.focus();
  await expect(noDraftCard).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(draftCard).toBeFocused();
  await page.keyboard.press("Enter");

  const contractName = page.getByLabel("계약 이름");
  await contractName.focus();
  await expect(contractName).toBeFocused();
  await page.keyboard.type("키보드 접근성 계약");
  const nextToSituation = page.getByRole("button", { name: "다음: 내 상황 알려주기" });
  await nextToSituation.focus();
  await expect(nextToSituation).toBeFocused();
  await page.keyboard.press("Enter");

  const contractType = page.getByRole("radio", { name: "전세" });
  await contractType.focus();
  await expect(contractType).toBeFocused();
  await page.keyboard.press("Space");

  const directLandlord = page.getByLabel("집주인이 직접 계약해요");
  await directLandlord.focus();
  await expect(directLandlord).toBeFocused();
  await page.keyboard.press("Space");
  await expect(directLandlord).toBeChecked();
  const dateToggle = page.getByRole("button", { name: "날짜를 입력할게요" });
  await dateToggle.focus();
  await expect(dateToggle).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.getByLabel("입주 예정일")).toBeVisible();
  const nextToUpload = page.getByRole("button", { name: "다음: 문서 준비하기" });
  await nextToUpload.focus();
  await expect(nextToUpload).toBeFocused();
  await page.keyboard.press("Enter");

  const contractPicker = page.getByRole("button", { name: "계약서 새 파일 선택" });
  const registryPicker = page.getByRole("button", { name: "등기사항증명서 새 파일 선택" });
  await contractPicker.focus();
  await expect(contractPicker).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(registryPicker).toBeFocused();
  await page.keyboard.press("Shift+Tab");
  await expect(contractPicker).toBeFocused();

  await page.getByLabel("계약서 사진 또는 파일 올리기")
    .setInputFiles(syntheticLeasePdfFixture);
  const startExtraction = page.getByRole("button", { name: "업로드하고 다음 단계로" });
  await startExtraction.focus();
  await expect(startExtraction).toBeFocused();
  await page.keyboard.press("Enter");

  const confirmCurrent = page.getByRole("button", { name: "네, 맞아요" });
  await expect(confirmCurrent).toBeVisible();
  await confirmCurrent.focus();
  await expect(confirmCurrent).toBeFocused();
  await page.keyboard.press("Enter");

  const editCurrent = page.getByRole("button", { name: "직접 고칠게요" });
  await editCurrent.focus();
  await expect(editCurrent).toBeFocused();
  await page.keyboard.press("Enter");
  const correction = page.locator('section[aria-label="내용 수정"]').locator("input, textarea");
  await correction.focus();
  await page.keyboard.press("Control+A");
  await page.keyboard.type("키보드로 수정한 내용");
  const saveCorrection = page.getByRole("button", { name: "수정한 내용 사용하기" });
  await saveCorrection.focus();
  await expect(saveCorrection).toBeFocused();
  await page.keyboard.press("Enter");

  const cannotVerify = page.getByRole("button", { name: "문서에서 확인하기 어려워요" });
  await cannotVerify.focus();
  await expect(cannotVerify).toBeFocused();
  await page.keyboard.press("Enter");
  const notStatedReason = page.getByLabel("문서에 적혀 있지 않아요");
  await notStatedReason.focus();
  await expect(notStatedReason).toBeFocused();
  await page.keyboard.press("Space");

  const previousReview = page.getByRole("button", { name: "이전 내용 보기" });
  await previousReview.focus();
  await expect(previousReview).toBeFocused();
  await page.keyboard.press("Enter");

  const sourceSummary = page.getByText("문서에서 읽은 전체 내용 보기");
  await sourceSummary.focus();
  await expect(sourceSummary).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(sourceSummary.locator("..")).toHaveAttribute("open", "");

  await confirmCurrent.focus();
  await page.keyboard.press("Enter");
  const completeHeading = page.getByRole("heading", {
    name: "중요한 내용을 모두 확인했습니다",
  });
  for (let attempt = 0; attempt < 40; attempt += 1) {
    if (await completeHeading.isVisible()) break;
    await confirmCurrent.focus();
    await expect(confirmCurrent).toBeFocused();
    await page.keyboard.press("Enter");
  }
  await expect(completeHeading).toBeVisible();

  const startAnalysis = page.getByRole("button", {
    name: "이 내용으로 확인 결과 준비하기",
  });
  await startAnalysis.focus();
  await expect(startAnalysis).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/analyzing\?analysisRunId=[^&]+$/);
  await expect(page.getByText("확인 결과 준비 완료").locator("xpath=ancestor::li")).toHaveAttribute("aria-current", "step");
  const reportButton = page.getByRole("button", { name: "확인 결과 보기" });
  await reportButton.focus();
  await expect(reportButton).toBeFocused();
  await page.keyboard.press("Enter");

  const firstActionLink = page.getByRole("link", { name: "첫 확인 행동으로 이동" });
  await firstActionLink.focus();
  await expect(firstActionLink).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/#first-action-item$/);

  const technicalSummary = page.getByText("세부 판정 정보").first();
  const technicalId = technicalSummary.locator("..").locator(".result-meta strong");
  await expect(technicalId).toBeHidden();
  await technicalSummary.focus();
  await expect(technicalSummary).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(technicalSummary.locator("..")).toHaveAttribute("open", "");
  await expect(technicalId).toBeVisible();

  const evidenceSummary = page.getByText("근거와 판정 한계 확인").first();
  await evidenceSummary.focus();
  await expect(evidenceSummary).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(evidenceSummary.locator("..")).toHaveAttribute("open", "");

  const checklistButton = page.getByRole("button", { name: "이제 할 일 확인하기" });
  await checklistButton.focus();
  await expect(checklistButton).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { name: "체크리스트와 계약 직후 행동" })).toBeVisible();
  if ((page.viewportSize()?.width ?? 0) <= 360) {
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
    expect(await page.locator("main.app-shell").evaluate((element) =>
      Number.parseFloat(getComputedStyle(element).paddingLeft),
    )).toBeGreaterThanOrEqual(16);
  }
});
