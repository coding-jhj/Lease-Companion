import { expect, test } from "@playwright/test";
import { syntheticLeasePdfFixture } from "./fixtures/syntheticLeasePdf";

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

async function confirmGuidedReview(page: import("@playwright/test").Page) {
  const completeHeading = page.getByRole("heading", {
    name: "중요한 내용을 모두 확인했습니다",
  });

  for (let attempt = 0; attempt < 80; attempt += 1) {
    if (await completeHeading.isVisible()) break;
    const confirmButton = page.getByRole("button", { name: "네, 맞아요" });
    await expect(confirmButton).toBeVisible();
    await confirmButton.click();
  }

  await expect(completeHeading).toBeVisible();
}

test("v1.9 signup through saved checklist follows the complete MVP flow", async ({ page }, testInfo) => {
  const isRealApi = testInfo.project.name.startsWith("real-api");
  let analysisPostCount = 0;
  page.on("request", (request) => {
    if (
      request.method() === "POST"
      && /\/api\/contracts\/\d+\/analysis-runs$/.test(new URL(request.url()).pathname)
    ) {
      analysisPostCount += 1;
    }
  });
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
  await expect(page.getByRole("heading", { name: "어떻게 시작할까요?" })).toBeVisible();
  await page.getByRole("link", { name: /실전 계약 점검/ }).click();
  await expect(page.getByRole("heading", { name: "지금 어떤 상황인가요?" })).toBeVisible();
  await page.getByRole("link", { name: /아직 계약서를 받지 않았어요/ }).click();
  await expect(page).toHaveURL(/\/prepare$/);
  await page.getByRole("link", { name: "계약서 초안 등을 받아 점검해 보기" }).click();
  await page.getByLabel("계약 이름").fill("E2E 전세 계약");
  await page.getByRole("button", { name: "다음: 내 상황 알려주기" }).click();
  await page.getByRole("radio", { name: "전세" }).check();
  await page.getByLabel("집주인이 직접 계약해요").check();
  await page.getByRole("button", { name: "다음: 문서 준비하기" }).click();
  await expect(page).toHaveURL(/\/upload$/);
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(0);

  expect(syntheticLeasePdfFixture.mimeType).toBe("application/pdf");
  expect(syntheticLeasePdfFixture.buffer.subarray(0, 5).toString("ascii")).toBe("%PDF-");
  const syntheticPdfAscii = syntheticLeasePdfFixture.buffer.toString("ascii");
  const startXref = /startxref\n(\d+)\n%%EOF\n$/.exec(syntheticPdfAscii);
  expect(startXref).not.toBeNull();
  expect(syntheticPdfAscii.slice(Number(startXref?.[1]), Number(startXref?.[1]) + 4))
    .toBe("xref");
  await page.getByLabel("계약서 사진 또는 파일 올리기")
    .setInputFiles(syntheticLeasePdfFixture);
  await expect(page.getByText(syntheticLeasePdfFixture.name)).toBeVisible();
  const uploadSubmit = page.getByRole("button", { name: "업로드하고 다음 단계로" });
  await uploadSubmit.scrollIntoViewIfNeeded();
  await expect(uploadSubmit).toBeEnabled();
  expect(await uploadSubmit.evaluate((element) => {
    const rect = element.getBoundingClientRect();
    const centerX = rect.left + rect.width / 2;
    const centerY = rect.top + rect.height / 2;
    return document.elementFromPoint(centerX, centerY) === element;
  })).toBeTruthy();
  // Playwright mobile auto-scroll can move this below the preceding dropzone after
  // the hit-test succeeds. Force avoids that second scroll while preserving the check.
  await uploadSubmit.click({ force: true });

  await expect(page.getByRole("heading", { name: "문서에서 읽은 내용 확인" })).toBeVisible();
  await expect(page.getByRole("button", { name: "네, 맞아요" })).toBeVisible();
  await confirmGuidedReview(page);
  expect(analysisPostCount).toBe(0);

  await page.getByRole("button", { name: "이 내용으로 확인 결과 준비하기" }).click();
  await expect(page).toHaveURL(/\/analyzing\?analysisRunId=[^&]+$/);
  await expect.poll(() => analysisPostCount).toBe(1);

  await expect(page.getByRole("heading", {
    level: 1,
    name: "확인 결과 준비 완료",
  })).toBeVisible();
  await page.getByRole("button", { name: "확인 결과 보기" }).click();
  const firstActionHeading = page.getByRole("heading", { name: "먼저 할 일" });
  const questionsHeading = page.getByRole("heading", { name: "상대방에게 물어볼 말" });
  const reasonsHeading = page.getByRole("heading", { name: "왜 확인해야 하나요?" });
  const referencesHeading = page.getByRole("heading", { name: "비슷한 상황에서 확인할 점" });
  for (const heading of [
    firstActionHeading,
    questionsHeading,
    reasonsHeading,
    referencesHeading,
  ]) {
    await expect(heading).toBeVisible();
  }
  const headingDomPositions = await page.evaluate(
    (ids) => ids.map((id) => {
      const element = document.getElementById(id);
      if (!element) throw new Error(`결과 섹션 제목을 찾지 못했습니다: ${id}`);
      return [...document.querySelectorAll("body *")].indexOf(element);
    }),
    ["action-first-title", "action-hub-title", "all-results-title", "damage-reference-title"],
  );
  expect(headingDomPositions).toEqual([...headingDomPositions].sort((left, right) => left - right));

  const viewport = page.viewportSize();
  if (viewport && viewport.width <= 360) {
    await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(0);
    for (const { label, locator } of [
      { label: "결과 hero 제목", locator: page.locator(".report-hero h2") },
      {
        label: "첫 행동 제목",
        locator: page.locator("#first-action-item .action-first__title"),
      },
      {
        label: "물어볼 말 진입 링크",
        locator: page.getByRole("link", { name: "물어볼 말 바로 보기" }),
      },
    ]) {
      const box = await locator.boundingBox();
      expect(box).not.toBeNull();
      expect(box?.y ?? -1, `${label}의 y 좌표`).toBeGreaterThanOrEqual(0);
      const visibleHeight = Math.min(
        box?.height ?? 0,
        viewport.height - (box?.y ?? viewport.height),
      );
      expect(visibleHeight, `${label}의 첫 viewport 노출 높이`)
        .toBeGreaterThan(0);
    }
    expect(await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    )).toBeTruthy();
  }
  if ((page.viewportSize()?.width ?? 0) >= 1024) {
    await expect(page.locator("main.app-shell")).toHaveClass(/app-shell--report/);
    await expect(page.locator(".report-results-column")).toBeVisible();
  }
  const allResults = page.locator('section[aria-labelledby="all-results-title"]');
  const firstTechnicalDetails = allResults.locator(".result-technical-details").first();
  const firstInternalId = firstTechnicalDetails.locator(".result-meta strong");
  await expect(firstInternalId).toBeHidden();
  await firstTechnicalDetails.getByText("세부 판정 정보").click();
  await expect(firstInternalId).toBeVisible();
  await expect(firstInternalId).toHaveText(/^[RJ]\d{2}$/);
  await expandAllResultGroups(page);
  for (const judgmentId of Array.from({ length: 12 }, (_, index) => `J${String(index + 1).padStart(2, "0")}`)) {
    await expect(allResults).toContainText(judgmentId);
  }
  await expect(allResults).not.toContainText("R01");
  await expect(allResults).toContainText("상태:");
  if (isRealApi) {
    const j10 = allResults.getByText("J10").locator("xpath=ancestor::article[1]");
    await expect(j10).toContainText("상태: 확인 필요");
    await expect(j10).toContainText("신규 임차인의 입주에 연동");

    const refundPattern = page.locator(".damage-patterns__row").filter({
      hasText: "보증금 반환 조건",
    });
    await expect(refundPattern).toContainText("관련 확인 신호 있음");
    await refundPattern.getByText("근거와 분석 한계").click();
    await expect(refundPattern.getByRole("heading", { name: "검증된 유사 참고 사례" })).toBeVisible();
    await expect(refundPattern.getByRole("link", { name: "계약기간 종료 후 보증금 미반환 유형" })).toBeVisible();
  }
  for (const title of [
    "중개사에게 물어볼 말",
    "임대인에게 물어볼 말",
    "내가 문서에서 다시 볼 것",
    "계약 전",
    "계약 중",
    "잔금·입주 당일",
    "계약 후",
    "보관할 자료",
  ]) {
    await expect(page.getByRole("heading", { name: title })).toBeVisible();
  }
  await expect(page.getByRole("button", { name: "확인 결과 PDF 저장" })).toBeVisible();
  await expect(page.getByRole("link", { name: "첫 확인 행동으로 이동" })).toBeVisible();

  await page.reload();
  await expect(page.getByRole("heading", { name: "상대방에게 물어볼 말" })).toBeVisible();
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

  expect(analysisPostCount).toBe(1);
  await page.getByRole("button", { name: "이제 할 일 확인하기" }).click();
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
    has: page.getByRole("heading", { name: "확인 결과 이력" }),
  });
  await expect(analysisHistory).toContainText("확인 결과 보기");
  expect(analysisPostCount).toBe(1);

  if (isRealApi) {
    await page.reload();
    await expect(completedAction).toHaveAttribute("aria-label", /확인 취소$/);
    await expect(analysisHistory).toContainText("확인 결과 보기");
  }

  await page.getByRole("link", { name: "대시보드로 돌아가기" }).click();
  const contractCard = page.locator("article.contract-card").filter({ hasText: "E2E 전세 계약" });
  const management = contractCard.locator("details");
  await expect(management).not.toHaveAttribute("open", "");
  await contractCard.getByText("계약 관리").click();
  await expect(management).toHaveAttribute("open", "");
  const deleteResponse = page.waitForResponse((response) =>
    response.request().method() === "DELETE" && /\/api\/contracts\/\d+$/.test(response.url()),
  );
  page.once("dialog", (dialog) => dialog.accept());
  await contractCard.getByRole("button", { name: "계약 삭제" }).click();
  expect((await deleteResponse).status()).toBe(204);
  if (isRealApi) await expect(contractCard).toHaveCount(0);
  else await expect(contractCard).toHaveCount(1);
});
