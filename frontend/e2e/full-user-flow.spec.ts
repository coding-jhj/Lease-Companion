import { expect, test } from "@playwright/test";

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

  await page.getByRole("link", { name: "새 계약 만들기" }).click();
  await page.getByLabel("계약 이름").fill("E2E 전세 계약");
  await page.getByRole("button", { name: "계약 상황 입력하기" }).click();
  await page.getByLabel("대리 계약 여부").selectOption("no");
  await page.getByRole("button", { name: "문서 업로드하기" }).click();

  await page.getByLabel("계약서 PDF").setInputFiles({
    name: "contract.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("synthetic lease contract"),
  });
  await page.getByRole("button", { name: "추출 시작하기" }).click();

  await expect(page.getByRole("heading", { name: "추출값 확인·수정" })).toBeVisible();
  await expect(page.getByLabel("보증금 반환 조항 원문 값")).toBeVisible();
  await expect(page.getByLabel("수리·원상복구 조항 원문 값")).toBeVisible();
  await expect(page.getByLabel("보증금 반환 조건 값")).toHaveCount(0);
  await expect(page.getByLabel("수리·원상복구 책임 값")).toHaveCount(0);
  await page.getByRole("button", { name: "읽힌 값 모두 확인" }).click();
  await page.getByLabel("입금 계좌 예금주 값").fill("이정훈");
  const secondMainClause = page.getByLabel("계약서 본문 주요 조항 2 값");
  if (await secondMainClause.count()) {
    await secondMainClause.fill("주요 설비 하자 수선은 임대인이 부담하고, 임차인에게 알린다.");
  }
  await page.getByRole("button", { name: "확인 완료하고 분석하기" }).click();

  await expect(page.getByRole("heading", { name: "분석 완료" })).toBeVisible();
  await page.getByRole("button", { name: "리포트 보기" }).click();
  await expect(page.getByRole("heading", { name: "확인 질문과 다음 행동" })).toBeVisible();
  const ruleResults = page.locator('section[aria-labelledby="rule-results-title"]');
  const clauseJudgments = page.locator('section[aria-labelledby="clause-judgments-title"]');
  for (const ruleId of Array.from({ length: 10 }, (_, index) => `R${String(index + 1).padStart(2, "0")}`)) {
    await expect(ruleResults).toContainText(ruleId);
  }
  for (const judgmentId of ["J10", "J11", "J12"]) {
    await expect(clauseJudgments).toContainText(judgmentId);
  }
  await expect(clauseJudgments).toContainText("상태:");
  await expect(page.getByText("안전한 기본 안내").first()).toBeVisible();

  await page.reload();
  await expect(page.getByRole("heading", { name: "확인 질문과 다음 행동" })).toBeVisible();
  await expect(ruleResults).toContainText("R01");
  await expect(ruleResults).toContainText("R10");
  await expect(clauseJudgments).toContainText("J10");
  await expect(clauseJudgments).toContainText("J12");

  if (!isRealApi) {
    await page.getByLabel("평점").selectOption("5");
    await page.getByRole("textbox", { name: "의견", exact: true }).fill("전체 흐름 확인 완료");
    await page.getByRole("button", { name: "의견 저장" }).click();
    await expect(page.getByRole("status")).toContainText("의견이 저장되었습니다.");
  }

  await page.getByRole("button", { name: "체크리스트로 이동" }).click();
  const checklistSection = page.locator("section.history-section").filter({
    has: page.getByRole("heading", { name: "서명 전 체크리스트" }),
  });
  const action = checklistSection.getByRole("checkbox").first();
  await expect(action).toBeVisible();
  if (!await action.isChecked()) await action.click();
  await expect(action).toBeChecked();
  const analysisHistory = page.locator("section.history-section").filter({
    has: page.getByRole("heading", { name: "분석 이력" }),
  });
  await expect(analysisHistory).toContainText("completed");

  if (isRealApi) {
    await page.reload();
    await expect(action).toBeChecked();
    await expect(analysisHistory).toContainText("completed");
  }
});
