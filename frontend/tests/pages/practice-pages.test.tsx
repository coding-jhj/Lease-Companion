// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { PracticeHomePage } from "../../src/pages/practice/PracticeHomePage";
import { PracticeResultPage } from "../../src/pages/practice/PracticeResultPage";
import { PracticeScenarioPage } from "../../src/pages/practice/PracticeScenarioPage";
import { PracticeSessionPage } from "../../src/pages/practice/PracticeSessionPage";
import { practiceService } from "../../src/services/practiceService";
import type {
  PracticeDialogueTurnDto,
  PracticeResultDto,
  PracticeScenarioDetailDto,
  PracticeScenarioSummaryDto,
  PracticeSessionDto,
  PracticeTurnResponseDto,
} from "../../src/types/api";

const scenarioCases = [
  ["PRACTICE-DEFERRED-REFUND-001", "후임 임차인 조건부 보증금 반환", "보증금은 신규 임차인이 입주한 후 반환한다."],
  ["PRACTICE-THIRD-PARTY-PAYMENT-001", "공인중개사 명의 계좌로 가계약금 송금 요구", "중개사 명의 계좌의 수령 권한을 확인한다."],
  ["PRACTICE-PROXY-AUTHORITY-001", "대리인 권한 자료 없는 계약 요구", "위임장과 인감증명서를 계약 전에 확인한다."],
] as const;

function summary(scenarioId: string, title: string): PracticeScenarioSummaryDto {
  return {
    scenario_id: scenarioId,
    scenario_version: "1.0.0",
    title,
    role: "공인중개사",
    difficulty: "기본",
    contract_stage: "서명 전",
    always_show_labels: ["가상 연습", "합성 시나리오"],
  };
}

function dialogueTurn(turnId = "TURN-01", prompt = "계약을 바로 진행하시겠습니까?"): PracticeDialogueTurnDto {
  return { turn_id: turnId, prompt, wait_sequence: [] };
}

function detail(scenarioId: string, title: string, clause: string): PracticeScenarioDetailDto {
  return {
    ...summary(scenarioId, title),
    synthetic_contract: {
      contract_type: "전세",
      signed: false,
      deposit_paid: false,
      property_address: "서울특별시 가온구 연습로 1",
      deposit: 200000000,
      monthly_rent: null,
      contract_payment: 20000000,
      balance_payment: 180000000,
      requested_provisional_payment: 0,
      contract_payment_date: "2026-07-25",
      balance_payment_date: "2026-08-31",
      move_in_date: "2026-08-31",
      start_date: "2026-08-31",
      end_date: "2028-08-30",
      landlord_name: "가상임대인",
      broker_name: "가상중개사",
      is_proxy_contract: scenarioId.includes("PROXY"),
      agent_name: scenarioId.includes("PROXY") ? "가상대리인" : null,
      agent_relationship: scenarioId.includes("PROXY") ? "친족" : null,
      proxy_authority_documents: [],
      account_holder: scenarioId.includes("THIRD-PARTY") ? "가상중개사" : "가상임대인",
      account_number_stored: false,
      registry_issue_date: "2026-07-22",
      registry_property_address: "서울특별시 가온구 연습로 1",
      owner_names: ["가상임대인"],
      is_joint_ownership: false,
      owner_shares: { 가상임대인: "1/1" },
      mortgage_present: false,
      mortgage_maximum_claim: null,
      deposit_return_clause: clause,
      rights_change_clause_present: true,
      special_clauses: [clause],
    },
    initial_turn: dialogueTurn(),
  };
}

function session(overrides: Partial<PracticeSessionDto> = {}): PracticeSessionDto {
  return {
    practice_session_id: "session-001",
    scenario_id: "PRACTICE-DEFERRED-REFUND-001",
    scenario_version: "1.0.0",
    status: "active",
    current_state: "TURN-01",
    current_turn: dialogueTurn(),
    confirmed_action_ids: [],
    selected_action: null,
    allowed_final_actions: ["진행", "추가 확인", "보류", "중단"],
    started_at: "2026-07-22T00:00:00Z",
    completed_at: null,
    ...overrides,
  };
}

function turnResponse(nextSession: PracticeSessionDto, category: "appropriate_check" | "no_response" | "needs_review" = "appropriate_check"): PracticeTurnResponseDto {
  return {
    practice_turn_id: "practice-turn-001",
    attempt_no: 1,
    evaluation: {
      schema_version: "1.9.0",
      turn_id: "TURN-01",
      answer_category: category,
      confirmed_action_ids: category === "appropriate_check" ? ["PA01"] : [],
      next_dialogue_state: nextSession.current_state,
      fallback_reason: category === "needs_review" ? "provider_timeout" : null,
      evidence_text: category === "appropriate_check" ? "자료를 확인하겠습니다." : null,
      verbal_reliance: "not_observed",
    },
    dialogue_response: category === "needs_review" ? "답변을 다시 말씀해 주세요." : "확인 요청을 반영했습니다.",
    session: nextSession,
  };
}

function renderScenario(scenarioId: string) {
  return render(
    <MemoryRouter initialEntries={[`/practice/scenarios/${scenarioId}`]}>
      <Routes>
        <Route path="/practice/scenarios/:scenarioId" element={<PracticeScenarioPage />} />
        <Route path="/practice/sessions/:sessionId" element={<p>대화 세션 진입 완료</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

function renderSession() {
  return render(
    <MemoryRouter initialEntries={["/practice/sessions/session-001"]}>
      <Routes>
        <Route path="/practice/sessions/:sessionId" element={<PracticeSessionPage />} />
        <Route path="/practice/sessions/:sessionId/result" element={<p>결과 화면 이동 완료</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

beforeEach(() => {
  vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue(undefined);
});

function mockDesktopKeyboard(matches: boolean) {
  vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches }));
}

describe("Practice scenario pages", () => {
  it("does not show synthetic-scenario wording while the home list is loading", () => {
    vi.spyOn(practiceService, "listScenarios").mockReturnValue(new Promise(() => {}));
    render(<MemoryRouter><PracticeHomePage /></MemoryRouter>);

    expect(screen.getByText("연습 목록을 불러오는 중")).toBeInTheDocument();
    expect(screen.queryByText(/합성 시나리오/)).not.toBeInTheDocument();
  });

  it("uses a non-numeric fallback card for an unregistered scenario", async () => {
    vi.spyOn(practiceService, "listScenarios").mockResolvedValue([
      summary("PRACTICE-UNKNOWN-999", "확인할 내용이 있는 계약 상황"),
    ]);
    render(<MemoryRouter><PracticeHomePage /></MemoryRouter>);

    const card = (await screen.findByRole("heading", { name: "확인할 내용이 있는 계약 상황" })).closest("article")!;
    expect(within(card).getByText("확인할 내용 살펴보기")).toBeInTheDocument();
    expect(within(card).queryByText(/확인 행동 \d+개/)).not.toBeInTheDocument();
    expect(within(card).queryByText("PRACTICE-UNKNOWN-999")).not.toBeInTheDocument();
  });

  it("shows mission-centered scenario cards without internal labels or answer data", async () => {
    vi.spyOn(practiceService, "listScenarios").mockResolvedValue(
      scenarioCases.map(([id, title]) => summary(id, title)),
    );
    render(<MemoryRouter><PracticeHomePage /></MemoryRouter>);

    expect(await screen.findByRole("heading", { name: "계약 상황을 미리 연습해 보세요" })).toBeInTheDocument();
    const list = await screen.findByRole("region", { name: "연습 시나리오 목록" });
    for (const [, title] of scenarioCases) {
      const card = within(list).getByRole("heading", { name: title }).closest("article")!;
      expect(within(card).getByText(/계약서에 적힌 반환 조건을 확인하고|돈을 보내기 전에 누구에게 무엇을 확인해야 하는지|계약 상대의 권한을 확인할 자료를 요청하고/)).toBeInTheDocument();
      expect(within(card).getByText("약 3분 · 확인 행동 3개")).toBeInTheDocument();
      expect(within(card).getByRole("link", { name: "상황 확인하기" })).toHaveClass("text-link");
      expect(within(card).getByRole("link", { name: "상황 확인하기" })).not.toHaveClass("button-link");
    }
    expect(screen.queryByText(/가상 연습|합성 시나리오|난이도|계약 단계|정답표|hidden_confirmation_signals|필수 의미/)).not.toBeInTheDocument();
  });

  it.each(scenarioCases)("renders and starts %s through the common detail page", async (scenarioId, title, clause) => {
    vi.spyOn(practiceService, "getScenario").mockResolvedValue(detail(scenarioId, title, clause));
    const createSession = vi.spyOn(practiceService, "createSession").mockResolvedValue(
      session({ practice_session_id: `session-${scenarioId}` }),
    );
    renderScenario(scenarioId);

    expect(await screen.findByRole("heading", { name: title })).toBeInTheDocument();
    expect(screen.getByText("오늘의 미션")).toBeInTheDocument();
    expect(screen.getByText(title)).toBeInTheDocument();
    expect(screen.queryByText("계약을 바로 진행하시겠습니까?")).not.toBeInTheDocument();
    expect(screen.queryByText("가상 연습")).not.toBeInTheDocument();
    expect(screen.queryByText("합성 시나리오")).not.toBeInTheDocument();
    const contractDetails = screen.getByText("참고할 계약 내용 보기").closest("details")!;
    expect(contractDetails).not.toHaveAttribute("open");
    expect(screen.getByText("서울특별시 가온구 연습로 1").closest("section")).toHaveAttribute("hidden");
    expect(screen.getByText(clause).closest("section")).toHaveAttribute("hidden");
    expect(screen.getByRole("button", { name: "연습 시작하기" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "연습 시작하기" }));

    await waitFor(() => expect(createSession).toHaveBeenCalledWith(scenarioId));
    expect(await screen.findByText("대화 세션 진입 완료")).toBeInTheDocument();
  });
});

describe("PracticeSessionPage", () => {
  beforeEach(() => {
    vi.spyOn(practiceService, "getScenario").mockResolvedValue(
      detail("PRACTICE-DEFERRED-REFUND-001", "보증금 반환 조건 확인", "후임 임차인의 보증금이 입금된 후 반환한다."),
    );
    vi.spyOn(practiceService, "getLatestMedia").mockResolvedValue(null);
    vi.spyOn(practiceService, "getMessages").mockResolvedValue({
      items: [],
      next_cursor: null,
      has_more: false,
    });
  });

  it("moves the shared broker avatar from speaking to listening", async () => {
    vi.spyOn(practiceService, "getSession").mockResolvedValue(session());
    const view = renderSession();

    expect(await screen.findByText("공인중개사가 말하고 있습니다")).toBeInTheDocument();
    const speakingVideo = view.getByTestId("practice-video");
    expect(speakingVideo).toHaveAttribute("src", "/practice/avatar/speaking.mp4");
    expect(speakingVideo).toHaveAttribute("poster");

    fireEvent.ended(speakingVideo!);
    expect(await screen.findByText("답변을 듣고 있습니다")).toBeInTheDocument();
    expect(view.container.querySelector("video")).toHaveAttribute("src", "/practice/avatar/listening.mp4");
  });

  it("keeps the session focused on one scene and one primary answer action", async () => {
    vi.spyOn(practiceService, "getSession").mockResolvedValue(session({ confirmed_action_ids: ["PA01"] }));
    renderSession();

    expect(await screen.findByText("미션 진행")).toBeInTheDocument();
    expect(screen.getByText("확인 행동 1 / 3")).toBeInTheDocument();
    expect(screen.queryByText("TURN-01")).not.toBeInTheDocument();
    expect(screen.queryByRole("progressbar", { name: "미션 진행률" })).not.toBeInTheDocument();
    expect(screen.getAllByRole("tab").map((tab) => tab.textContent)).toEqual(["계약서", "대화 내용"]);
    expect(screen.queryByText("서울특별시 가온구 연습로 1")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "계약서" }));
    expect(screen.getByText("서울특별시 가온구 연습로 1")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "이렇게 말할게요" })).toHaveClass("primary");
    expect(document.querySelectorAll("button.primary")).toHaveLength(1);
  });

  it("shows the current prompt and keeps the hint as a secondary action", async () => {
    vi.spyOn(practiceService, "getSession").mockResolvedValue(session());
    renderSession();

    expect(await screen.findByRole("heading", { name: "계약을 바로 진행하시겠습니까?" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "말할 내용 힌트 보기" })).toHaveClass("secondary");
    expect(screen.queryByText("확인 대상")).not.toBeInTheDocument();
  });

  it("does not expose the actual next fixture turn while the first scene is active", async () => {
    const currentPrompt = "임대인분은 특약대로 다음 세입자가 들어오면 보증금을 바로 반환하겠다고 하십니다. 이 조건으로 진행해도 괜찮으시죠?";
    const futurePrompt = "임대인분 말씀으로는 새 세입자는 금방 구해질 테니 걱정하지 않으셔도 된다고 합니다. 구두로도 확실히 약속하셨습니다.";
    vi.spyOn(practiceService, "getSession").mockResolvedValue(session({
      current_turn: dialogueTurn("TURN-01", currentPrompt),
    }));
    renderSession();

    expect(await screen.findByRole("heading", { name: currentPrompt })).toBeInTheDocument();
    expect(document.body).not.toHaveTextContent(futurePrompt);
    expect(document.body).not.toHaveTextContent(/TURN-|answer key/i);
  });

  it("loads older saved conversation turns from the top of the chat", async () => {
    vi.spyOn(practiceService, "getSession").mockResolvedValue(session({
      current_state: "TURN-03",
      current_turn: dialogueTurn("TURN-03", "마지막으로 확인할 내용입니다."),
    }));
    const getMessages = vi.mocked(practiceService.getMessages);
    getMessages.mockReset();
    getMessages
      .mockResolvedValueOnce({
        items: [{
          practice_turn_id: "turn-002",
          turn_id: "TURN-02",
          prompt: "두 번째 질문입니다.",
          user_answer: "두 번째 답변입니다.",
          timed_out: false,
          dialogue_response: "확인했습니다.",
          created_at: "2026-07-23T00:00:02Z",
        }],
        next_cursor: "turn-002",
        has_more: true,
      })
      .mockResolvedValueOnce({
        items: [{
          practice_turn_id: "turn-001",
          turn_id: "TURN-01",
          prompt: "첫 번째 질문입니다.",
          user_answer: "첫 번째 답변입니다.",
          timed_out: false,
          dialogue_response: null,
          created_at: "2026-07-23T00:00:01Z",
        }],
        next_cursor: null,
        has_more: false,
      });

    renderSession();
    fireEvent.click(await screen.findByText("이전 대화 보기"));
    expect(await screen.findByText("두 번째 답변입니다.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "이전 대화 불러오기" }));

    expect(await screen.findByText("첫 번째 답변입니다.")).toBeInTheDocument();
    expect(getMessages).toHaveBeenLastCalledWith("session-001", "turn-002");
    expect(screen.getByText("대화의 시작입니다")).toBeInTheDocument();
  });

  it("restores the current turn, submits an answer, and renders the next turn", async () => {
    vi.spyOn(practiceService, "getSession").mockResolvedValue(session());
    const next = session({ current_state: "TURN-02", current_turn: dialogueTurn("TURN-02", "권한 자료도 필요할까요?"), confirmed_action_ids: ["PA01"] });
    const submit = vi.spyOn(practiceService, "submitTurn").mockResolvedValue(turnResponse(next));
    renderSession();

    fireEvent.change(await screen.findByLabelText("내 답변"), { target: { value: " 자료를 확인하고 보류하겠습니다. " } });
    fireEvent.click(screen.getByRole("button", { name: "이렇게 말할게요" }));

    await waitFor(() => expect(submit).toHaveBeenCalledWith("session-001", expect.objectContaining({
      turn_id: "TURN-01",
      user_answer: "자료를 확인하고 보류하겠습니다.",
      timed_out: false,
    })));
    expect(await screen.findByRole("heading", { name: "권한 자료도 필요할까요?" })).toBeInTheDocument();
    expect(screen.getByText("확인 행동 1 / 3")).toBeInTheDocument();
    fireEvent.click(screen.getByText("이전 대화 보기"));
    expect(await screen.findByText("자료를 확인하고 보류하겠습니다.")).toBeInTheDocument();
    expect(screen.getAllByText("권한 자료도 필요할까요?")).toHaveLength(2);
    // 응답 대사는 아바타 화면이 이미 말한다. 대화 기록에 또 넣으면 두 번 말한 것처럼 읽힌다.
    expect(within(screen.getByRole("tabpanel", { name: "지금까지의 대화" })).queryByText("확인 요청을 반영했습니다.")).toBeNull();
    expect(screen.queryByText("필요한 확인 행동이 전달되었습니다.")).not.toBeInTheDocument();
  });

  it("submits a non-empty answer with Enter on a PC keyboard", async () => {
    mockDesktopKeyboard(true);
    vi.spyOn(practiceService, "getSession").mockResolvedValue(session());
    const submit = vi.spyOn(practiceService, "submitTurn").mockResolvedValue(turnResponse(session({ current_state: "TURN-02", current_turn: dialogueTurn("TURN-02") })));
    renderSession();

    const textarea = await screen.findByLabelText("내 답변");
    fireEvent.change(textarea, { target: { value: "계약 조건을 확인하겠습니다." } });
    expect(screen.getByText("Enter로 보내기 · Shift+Enter로 줄바꿈")).toHaveClass("practice-answer-shortcut");
    fireEvent.keyDown(textarea, { key: "Enter" });

    await waitFor(() => expect(submit).toHaveBeenCalledTimes(1));
    expect(submit).toHaveBeenCalledWith("session-001", expect.objectContaining({ user_answer: "계약 조건을 확인하겠습니다." }));
  });

  it.each([
    ["Shift+Enter", true, { key: "Enter", shiftKey: true }],
    ["IME composition Enter", true, { key: "Enter", isComposing: true }],
    ["mobile Enter", false, { key: "Enter" }],
  ])("does not submit with %s", async (_label, desktopKeyboard, keyboardEvent) => {
    mockDesktopKeyboard(desktopKeyboard);
    vi.spyOn(practiceService, "getSession").mockResolvedValue(session());
    const submit = vi.spyOn(practiceService, "submitTurn");
    renderSession();

    const textarea = await screen.findByLabelText("내 답변");
    fireEvent.change(textarea, { target: { value: "계약 조건을 확인하겠습니다." } });
    fireEvent.keyDown(textarea, keyboardEvent);

    expect(submit).not.toHaveBeenCalled();
  });

  it("does not submit an empty answer or submit twice while a PC request is pending", async () => {
    mockDesktopKeyboard(true);
    vi.spyOn(practiceService, "getSession").mockResolvedValue(session());
    const submit = vi.spyOn(practiceService, "submitTurn").mockReturnValue(new Promise(() => {}));
    renderSession();

    const textarea = await screen.findByLabelText("내 답변");
    fireEvent.keyDown(textarea, { key: "Enter" });
    expect(submit).not.toHaveBeenCalled();

    fireEvent.change(textarea, { target: { value: "계약 조건을 확인하겠습니다." } });
    fireEvent.keyDown(textarea, { key: "Enter" });
    fireEvent.keyDown(textarea, { key: "Enter" });
    expect(submit).toHaveBeenCalledTimes(1);
  });

  it("submits a timeout without answer text and keeps the same turn", async () => {
    vi.spyOn(practiceService, "getSession").mockResolvedValue(session());
    const submit = vi.spyOn(practiceService, "submitTurn").mockResolvedValue(turnResponse(session(), "no_response"));
    renderSession();

    fireEvent.click(await screen.findByRole("button", { name: "답변하지 못했어요" }));

    await waitFor(() => expect(submit).toHaveBeenCalledWith("session-001", expect.objectContaining({
      turn_id: "TURN-01",
      user_answer: null,
      timed_out: true,
    })));
    expect(screen.getByRole("heading", { name: "계약을 바로 진행하시겠습니까?" })).toBeInTheDocument();
  });

  it("explains a provider review fallback and allows the same turn to be retried", async () => {
    vi.spyOn(practiceService, "getSession").mockResolvedValue(session());
    vi.spyOn(practiceService, "submitTurn").mockResolvedValue(turnResponse(session(), "needs_review"));
    renderSession();

    fireEvent.change(await screen.findByLabelText("내 답변"), { target: { value: "자료를 확인하겠습니다." } });
    fireEvent.click(screen.getByRole("button", { name: "이렇게 말할게요" }));

    expect(await screen.findByRole("heading", { name: "계약을 바로 진행하시겠습니까?" })).toBeInTheDocument();
    fireEvent.click(screen.getByText("이전 대화 보기"));
    const conversation = await screen.findByRole("tabpanel", { name: "지금까지의 대화" });
    expect(within(conversation).getAllByText("계약을 바로 진행하시겠습니까?")).toHaveLength(2);
    expect(within(conversation).queryByText("답변을 다시 말씀해 주세요.")).toBeNull();
    expect(screen.getByRole("alert")).toHaveTextContent(
      "답변을 확인하지 못했습니다. 입력한 내용은 잘못된 답변으로 처리하지 않았습니다. 연습은 계속할 수 있습니다.",
    );
    expect(screen.getByRole("button", { name: "다시 확인하기" })).toHaveClass("secondary");
    expect(screen.getByRole("button", { name: "다음 상황으로" })).toHaveClass("secondary");
    expect(document.body).not.toHaveTextContent("provider_timeout");
    expect(document.body).not.toHaveTextContent("case_id");
    const retryAnswer = screen.getByLabelText("내 답변");
    expect(retryAnswer).toBeEnabled();
    expect(retryAnswer).toHaveValue("");
    fireEvent.change(retryAnswer, { target: { value: "같은 내용을 다시 확인하겠습니다." } });
    expect(screen.getByRole("button", { name: "이렇게 말할게요" })).toBeEnabled();
  });

  it("treats a response validation failure as a non-answer fallback", async () => {
    vi.spyOn(practiceService, "getSession").mockResolvedValue(session());
    const invalidResponse = turnResponse(session(), "needs_review");
    invalidResponse.evaluation.fallback_reason = "response_validation_failed";
    vi.spyOn(practiceService, "submitTurn").mockResolvedValue(invalidResponse);
    renderSession();

    fireEvent.change(await screen.findByLabelText("내 답변"), { target: { value: "자료를 확인하겠습니다." } });
    fireEvent.click(screen.getByRole("button", { name: "이렇게 말할게요" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "답변을 확인하지 못했습니다. 입력한 내용은 잘못된 답변으로 처리하지 않았습니다. 연습은 계속할 수 있습니다.",
    );
    expect(screen.getByRole("button", { name: "다시 확인하기" })).toBeVisible();
    expect(screen.getByLabelText("내 답변")).toBeEnabled();
  });

  it("preserves the typed answer after a network error", async () => {
    vi.spyOn(practiceService, "getSession").mockResolvedValue(session());
    vi.spyOn(practiceService, "submitTurn").mockRejectedValue(new Error("네트워크 연결을 확인해 주세요."));
    renderSession();

    const answer = await screen.findByLabelText("내 답변");
    fireEvent.change(answer, { target: { value: "권한 자료를 확인하겠습니다." } });
    fireEvent.click(screen.getByRole("button", { name: "이렇게 말할게요" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("답변을 보내지 못했습니다. 입력한 답변은 그대로 남아 있습니다. 다시 시도해 주세요.");
    expect(answer).toHaveValue("권한 자료를 확인하겠습니다.");
    expect(screen.getByRole("button", { name: "이렇게 말할게요" })).toBeEnabled();
  });

  it("submits only an allowed final action and navigates to the result", async () => {
    const actionSession = session({ current_state: "ACTION-SELECTION", current_turn: null, confirmed_action_ids: ["PA01", "PA02"] });
    vi.spyOn(practiceService, "getSession").mockResolvedValue(actionSession);
    const submit = vi.spyOn(practiceService, "submitFinalAction").mockResolvedValue({
      practice_turn_id: "final-turn-001",
      attempt_no: 1,
      evaluation: null,
      dialogue_response: null,
      session: session({ status: "completed", current_state: "DEBRIEF", current_turn: null, selected_action: "보류", completed_at: "2026-07-22T00:10:00Z" }),
    });
    renderSession();

    const finalSection = (await screen.findByRole("heading", { name: "연습 결과 확인하기" })).closest("section")!;
    expect(within(finalSection).getAllByRole("button").map((button) => button.textContent)).toEqual(["진행", "추가 확인", "보류", "중단", "연습 결과 확인하기"]);
    expect(screen.queryByText(/최종 행동/)).not.toBeInTheDocument();
    fireEvent.click(within(finalSection).getByRole("button", { name: "보류" }));
    expect(within(finalSection).getByRole("button", { name: "연습 결과 확인하기" })).toHaveClass("primary");
    fireEvent.click(within(finalSection).getByRole("button", { name: "연습 결과 확인하기" }));

    await waitFor(() => expect(submit).toHaveBeenCalledWith("session-001", expect.objectContaining({ selected_action: "보류" })));
    expect(await screen.findByText("결과 화면 이동 완료")).toBeInTheDocument();
  });

  it("moves to the next situation after a provider fallback without recording an answer", async () => {
    vi.spyOn(practiceService, "getSession").mockResolvedValue(session());
    vi.spyOn(practiceService, "submitTurn").mockResolvedValue(turnResponse(session(), "needs_review"));
    const advance = vi.spyOn(practiceService, "advanceDialogue").mockResolvedValue(
      turnResponse(session({ current_state: "TURN-02", current_turn: dialogueTurn("TURN-02", "다음 확인 상황입니다.") })),
    );
    renderSession();

    fireEvent.change(await screen.findByLabelText("내 답변"), { target: { value: "자료를 확인하겠습니다." } });
    fireEvent.click(screen.getByRole("button", { name: "이렇게 말할게요" }));
    fireEvent.click(await screen.findByRole("button", { name: "다음 상황으로" }));

    await waitFor(() => expect(advance).toHaveBeenCalledWith("session-001", expect.objectContaining({
      turn_id: "TURN-01",
      destination: "next_turn",
    })));
    expect(await screen.findByRole("heading", { name: "다음 확인 상황입니다." })).toBeInTheDocument();
  });

  it("redirects a restored completed session to its result", async () => {
    vi.spyOn(practiceService, "getSession").mockResolvedValue(
      session({ status: "completed", current_state: "DEBRIEF", current_turn: null, selected_action: "보류", completed_at: "2026-07-22T00:10:00Z" }),
    );
    renderSession();
    expect(await screen.findByText("결과 화면 이동 완료")).toBeInTheDocument();
  });
});

describe("PracticeResultPage", () => {
  it("renders user-facing official source names without exposing internal IDs", async () => {
    const result: PracticeResultDto = {
      schema_version: "1.9.0",
      session_id: "session-001",
      scenario_id: "PRACTICE-DEFERRED-REFUND-001",
      scenario_version: "1.0.0",
      selected_action: "보류",
      confirmed_action_ids: ["PA01"],
      missed_action_ids: ["PA02"],
      confirmed_actions: ["반환 조건을 확인함"],
      missed_signals: ["구두 약속만으로 진행하지 않기"],
      recommended_phrases: ["반환 조건을 특약에 적어 주세요."],
      next_actions: ["수정된 특약을 다시 확인합니다."],
      official_source_ids: ["SRC-STD-LEASE", "SRC-HTA-LAW", "SRC-UNKNOWN", "SRC-UNKNOWN"],
    };
    vi.spyOn(practiceService, "getResult").mockResolvedValue({ result });
    render(
      <MemoryRouter initialEntries={["/practice/sessions/session-001/result"]}>
        <Routes><Route path="/practice/sessions/:sessionId/result" element={<PracticeResultPage />} /></Routes>
      </MemoryRouter>,
    );

    expect(await screen.findByRole("heading", { name: "보류" })).toBeInTheDocument();
    expect(screen.getByText("반환 조건을 확인함")).toBeInTheDocument();
    expect(screen.getByText("구두 약속만으로 진행하지 않기")).toBeInTheDocument();
    expect(screen.getByText("반환 조건을 특약에 적어 주세요.")).toBeInTheDocument();
    expect(screen.getByText("수정된 특약을 다시 확인합니다.")).toBeInTheDocument();
    expect(screen.getByText("주택임대차 표준계약서")).toBeInTheDocument();
    expect(screen.getByText("주택임대차보호법")).toBeInTheDocument();
    expect(screen.getAllByText("공식 자료")).toHaveLength(1);
    expect(screen.queryByText(/^SRC-/)).not.toBeInTheDocument();
    expect(screen.queryByText(/안전 점수|위험 점수|사기 가능성/)).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "같은 상황 다시 연습" })).toHaveAttribute("href", "/practice/scenarios/PRACTICE-DEFERRED-REFUND-001");
  });
});
