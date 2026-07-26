import { expect, test } from "@playwright/test";
import { syntheticLeasePdfFixture } from "./fixtures/syntheticLeasePdf";

async function finishReviewWithKeyboard(page: import("@playwright/test").Page) {
  const completeHeading = page.getByRole("heading", {
    name: "중요한 내용을 모두 확인했습니다",
  });
  const sectionButtons = page
    .getByRole("navigation", { name: "확인 묶음" })
    .getByRole("button");

  for (let guard = 0; guard < 200; guard += 1) {
    if (await completeHeading.isVisible()) break;

    const confirmButton = page.getByRole("button", { name: "네, 맞아요" }).first();
    if (await confirmButton.isVisible()) {
      await confirmButton.focus();
      await expect(confirmButton).toBeFocused();
      await page.keyboard.press("Enter");
      continue;
    }

    const bulkButton = page.getByRole("button", { name: /^\d+개 모두 네, 맞아요$/ });
    if (await bulkButton.isVisible() && await bulkButton.isEnabled()) {
      await bulkButton.focus();
      await expect(bulkButton).toBeFocused();
      await page.keyboard.press("Enter");
      continue;
    }

    const advanceButton = page.getByRole("button", {
      name: /^(다음 구역:|남은 구역:|전체 확인 내용 보기)/,
    });
    if (await advanceButton.isVisible() && await advanceButton.isEnabled()) {
      await advanceButton.focus();
      await expect(advanceButton).toBeFocused();
      await page.keyboard.press("Enter");
      continue;
    }

    let movedToPendingSection = false;
    for (let index = 0; index < await sectionButtons.count(); index += 1) {
      const sectionButton = sectionButtons.nth(index);
      const progress = (await sectionButton.innerText()).match(/(\d+)\s*\/\s*(\d+)/);
      if (progress && Number(progress[1]) < Number(progress[2])) {
        await sectionButton.focus();
        await expect(sectionButton).toBeFocused();
        await page.keyboard.press("Enter");
        movedToPendingSection = true;
        break;
      }
    }
    if (!movedToPendingSection) break;
  }

  await expect(completeHeading).toBeVisible();
}

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
  const nextToUpload = page.getByRole("button", { name: "다음: 문서 올리기" });
  await nextToUpload.focus();
  await expect(nextToUpload).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/upload$/);

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

  const situationSection = page.getByRole("button", { name: /3 직접 알려주실 내용/ });
  await situationSection.focus();
  await expect(situationSection).toBeFocused();
  await page.keyboard.press("Enter");

  const contractType = page.getByRole("radio", { name: "전세" });
  await contractType.focus();
  await expect(contractType).toBeFocused();
  await page.keyboard.press("Space");
  await expect(contractType).toBeChecked();

  const directLandlord = page.getByRole("radio", { name: "집주인이 직접 계약해요" });
  await directLandlord.focus();
  await expect(directLandlord).toBeFocused();
  await page.keyboard.press("Space");
  await expect(directLandlord).toBeChecked();

  const moveInDate = page.getByLabel("입주 예정일");
  await moveInDate.focus();
  await expect(moveInDate).toBeFocused();

  const firstReviewSection = page.getByRole("button", { name: /1 금전 피해/ });
  await firstReviewSection.focus();
  await expect(firstReviewSection).toBeFocused();
  await page.keyboard.press("Enter");

  const confirmCurrent = page.getByRole("button", { name: "네, 맞아요" }).first();
  await expect(confirmCurrent).toBeVisible();
  await confirmCurrent.focus();
  await expect(confirmCurrent).toBeFocused();
  await page.keyboard.press("Enter");

  const editCurrent = page.getByRole("button", { name: "직접 고칠게요" }).first();
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

  // 확인 구역 항목을 한 번에 보여주면서 같은 버튼이 여러 개 노출된다. 첫 항목으로 확인한다.
  const cannotVerify = page.getByRole("button", { name: "문서에서 확인하기 어려워요" }).first();
  // 수정 저장 요청이 끝나기 전에는 버튼이 비활성이라 포커스가 들어가지 않는다.
  await expect(cannotVerify).toBeEnabled();
  await cannotVerify.focus();
  await expect(cannotVerify).toBeFocused();
  await page.keyboard.press("Enter");
  const notStatedReason = page.getByLabel("문서에 적혀 있지 않아요");
  await notStatedReason.focus();
  await expect(notStatedReason).toBeFocused();
  await page.keyboard.press("Space");

  await finishReviewWithKeyboard(page);

  const previousReview = page.getByRole("button", { name: "이전 내용 보기" });
  await previousReview.focus();
  await expect(previousReview).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("navigation", { name: "확인 묶음" })).toBeVisible();
  const finishReview = page.getByRole("button", { name: "전체 확인 내용 보기" });
  await finishReview.focus();
  await expect(finishReview).toBeFocused();
  await page.keyboard.press("Enter");
  const completeHeading = page.getByRole("heading", {
    name: "중요한 내용을 모두 확인했습니다",
  });
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

  // 탭은 화살표 키로 이동하고, 이동한 탭이 그대로 선택된다.
  const itemsTab = page.getByRole("tab", { name: "확인 항목" });
  await itemsTab.focus();
  await expect(itemsTab).toBeFocused();
  await page.keyboard.press("ArrowRight");
  const questionsTab = page.getByRole("tab", { name: "확인할 내용" });
  await expect(questionsTab).toBeFocused();
  await expect(questionsTab).toHaveAttribute("aria-selected", "true");
  await page.keyboard.press("ArrowLeft");
  await expect(itemsTab).toBeFocused();
  await expect(itemsTab).toHaveAttribute("aria-selected", "true");

  // 접힘이 하나로 합쳐져 판정 id·근거를 같은 자리에서 연다.
  const detailSummary = page.getByText("자세히 보기").first();
  const technicalId = detailSummary.locator("..").locator(".result-meta strong");
  await expect(technicalId).toBeHidden();
  await detailSummary.focus();
  await expect(detailSummary).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(detailSummary.locator("..")).toHaveAttribute("open", "");
  await expect(technicalId).toBeVisible();
  await expect(detailSummary.locator("..").getByText("확인 한계")).toBeVisible();

  const checklistButton = page.getByRole("button", { name: "이제 할 일 확인하기" });
  await checklistButton.focus();
  await expect(checklistButton).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { name: "체크리스트와 계약 후 행동" })).toBeVisible();
  if ((page.viewportSize()?.width ?? 0) <= 360) {
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
    expect(await page.locator("main.app-shell").evaluate((element) =>
      Number.parseFloat(getComputedStyle(element).paddingLeft),
    )).toBeGreaterThanOrEqual(16);
  }
});
