// @vitest-environment jsdom
import "@testing-library/jest-dom/vitest";

import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
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
  PracticeSelectedAction,
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

function turnResponse(
  nextSession: PracticeSessionDto,
  category: "appropriate_check" | "partial_check" | "ambiguous_answer" | "no_response" | "needs_review" = "appropriate_check",
  actionIntent: PracticeSelectedAction | null = null,
): PracticeTurnResponseDto {
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
      dialogue_intent: null,
      action_intent: actionIntent,
    },
    dialogue_response:
      category === "needs_review"
        ? "답변을 다시 말씀해 주세요."
        : category === "no_response"
          ? "답변이 없으면 기존 특약 문구를 유지하겠습니다."
          : category === "ambiguous_answer"
            ? "말씀하신 뜻이 분명하지 않은데, 앞서 안내드린 조건대로 진행해도 될까요?"
            : category === "partial_check"
              ? "말씀하신 취지는 알겠지만, 그 부분은 나중에 확인하고 우선 진행하시죠."
          : "확인 요청을 반영했습니다.",
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
    expect(within(card).getByText("약 3분 · 대화 후 주의사항 안내")).toBeInTheDocument();
    expect(within(card).queryByText(/확인 행동 \d+개/)).not.toBeInTheDocument();
    expect(within(card).queryByText("PRACTICE-UNKNOWN-999")).not.toBeInTheDocument();
  });

  it("shows conversation-centered scenario cards without internal labels or answer data", async () => {
    vi.spyOn(practiceService, "listScenarios").mockResolvedValue(
      scenarioCases.map(([id, title]) => summary(id, title)),
    );
    render(<MemoryRouter><PracticeHomePage /></MemoryRouter>);

    expect(await screen.findByRole("heading", { name: "계약 상황을 미리 연습해 보세요" })).toBeInTheDocument();
    const list = await screen.findByRole("region", { name: "연습 시나리오 목록" });
    for (const [, title] of scenarioCases) {
      const card = within(list).getByRole("heading", { name: title }).closest("article")!;
      expect(within(card).getByText("상대방의 제안을 직접 들어보고 자유롭게 답해 보는 대화입니다.")).toBeInTheDocument();
      expect(within(card).getByText("약 3분 · 대화 후 주의사항 안내")).toBeInTheDocument();
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
    let finishInitialMedia!: (value: null) => void;
    vi.spyOn(practiceService, "getLatestMedia").mockReturnValue(
      new Promise((resolve) => {
        finishInitialMedia = resolve;
      }),
    );
    renderScenario(scenarioId);

    expect(await screen.findByRole("heading", { name: title })).toBeInTheDocument();
    expect(screen.getByText(/주의사항은 대화가 끝난 뒤 보여드립니다\./)).toBeInTheDocument();
    expect(screen.getByText(/실제 피해 사례와 유사한 상황에서 공인중개사와 대화하며, 금전 피해를 예방하기 위해 필요한 질문과 대응 방법을 연습해 보세요\./)).toBeInTheDocument();
    expect(screen.queryByText("오늘의 미션")).not.toBeInTheDocument();
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
    expect(await screen.findByText("시뮬레이션 준비중입니다. 잠시만 기다려주세요.")).toBeInTheDocument();
    finishInitialMedia(null);
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

    expect(await screen.findByRole("heading", { name: "계약을 바로 진행하시겠습니까?" })).toBeInTheDocument();
    expect(screen.queryByText("미션 진행")).not.toBeInTheDocument();
    expect(screen.queryByText(/확인 행동 \d+ \/ \d+/)).not.toBeInTheDocument();
    expect(screen.queryByText("TURN-01")).not.toBeInTheDocument();
    expect(screen.queryByRole("progressbar", { name: "미션 진행률" })).not.toBeInTheDocument();
    expect(screen.getAllByRole("tab").map((tab) => tab.textContent)).toEqual(["계약서", "대화 내용"]);
    expect(screen.queryByText("서울특별시 가온구 연습로 1")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "계약서" }));
    expect(screen.getByText("서울특별시 가온구 연습로 1")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "전송" })).toHaveClass("primary");
    expect(document.querySelectorAll("button.primary")).toHaveLength(1);
  });

  it("fills the answer with Korean browser speech recognition", async () => {
    class MockSpeechRecognition {
      static latest: MockSpeechRecognition | null = null;
      lang = "";
      continuous = true;
      interimResults = false;
      onresult: ((event: { results: ArrayLike<{ readonly 0: { readonly transcript: string } }> }) => void) | null = null;
      onerror: ((event: { error: string }) => void) | null = null;
      onend: (() => void) | null = null;
      start = vi.fn();
      stop = vi.fn();
      abort = vi.fn();

      constructor() {
        MockSpeechRecognition.latest = this;
      }
    }

    vi.stubGlobal("SpeechRecognition", MockSpeechRecognition);
    vi.spyOn(practiceService, "getSession").mockResolvedValue(session());
    renderSession();

    fireEvent.click(await screen.findByRole("button", { name: "말하기" }));
    const recognition = MockSpeechRecognition.latest!;
    expect(recognition.start).toHaveBeenCalledOnce();
    expect(recognition.lang).toBe("ko-KR");
    expect(recognition.interimResults).toBe(true);
    expect(screen.getByRole("button", { name: "듣는 중…" })).toHaveAttribute("aria-pressed", "true");

    act(() => {
      recognition.onresult?.({
        results: [{ 0: { transcript: "계약 조건을 먼저 확인하겠습니다" } }],
      });
    });
    expect(screen.getByLabelText("내 답변")).toHaveValue("계약 조건을 먼저 확인하겠습니다");

    act(() => recognition.onend?.());
    expect(screen.getByRole("button", { name: "말하기" })).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByText("음성 입력이 완료되었습니다.")).toBeInTheDocument();
  });

  it("shows the current prompt without mission or answer coaching", async () => {
    vi.spyOn(practiceService, "getSession").mockResolvedValue(session());
    renderSession();

    expect(await screen.findByRole("heading", { name: "계약을 바로 진행하시겠습니까?" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "말할 내용 힌트 보기" })).not.toBeInTheDocument();
    expect(screen.queryByText("오늘의 미션")).not.toBeInTheDocument();
    expect(screen.queryByText("확인 대상")).not.toBeInTheDocument();
  });

  it("shows the opening broker prompt in an otherwise empty conversation", async () => {
    vi.spyOn(practiceService, "getSession").mockResolvedValue(session());
    renderSession();

    fireEvent.click(await screen.findByText("이전 대화 보기"));
    const conversation = await screen.findByRole("tabpanel", { name: "지금까지의 대화" });

    expect(within(conversation).getByText("계약을 바로 진행하시겠습니까?")).toBeInTheDocument();
    expect(within(conversation).getByText("공인중개사")).toBeInTheDocument();
    expect(within(conversation).queryByText("아직 주고받은 답변이 없습니다.")).not.toBeInTheDocument();
    expect(within(conversation).getByText("대화의 시작입니다")).toBeInTheDocument();
    expect(within(conversation).getByText("0개 답변")).toBeInTheDocument();
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
    getMessages.mockImplementation(async (_sessionId, before, limit) => {
      if (before === "turn-002") {
        return {
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
        };
      }
      return {
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
        has_more: limit !== 1,
      };
    });

    renderSession();
    fireEvent.click(await screen.findByText("이전 대화 보기"));
    expect(await screen.findByText("두 번째 답변입니다.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "이전 대화 불러오기" }));

    expect(await screen.findByText("첫 번째 답변입니다.")).toBeInTheDocument();
    expect(getMessages).toHaveBeenLastCalledWith("session-001", "turn-002");
    expect(screen.getByText("대화의 시작입니다")).toBeInTheDocument();
  });

  it("does not replay media from a previous turn after reloading the session", async () => {
    vi.spyOn(practiceService, "getSession").mockResolvedValue(session({
      current_state: "TURN-02",
      current_turn: dialogueTurn("TURN-02", "현재 두 번째 질문입니다."),
    }));
    vi.mocked(practiceService.getLatestMedia).mockResolvedValue({
      media_job_id: "media-old",
      practice_turn_id: "practice-turn-old",
      media_kind: "dialogue_response",
      status: "failed",
      provider: "local",
      speech_text: "이전 질문의 중개사 반응입니다.",
      audio_url: null,
      video_url: null,
      error_code: "media_generation_failed",
      created_at: "2026-07-23T00:00:01Z",
      completed_at: "2026-07-23T00:00:02Z",
    });
    vi.mocked(practiceService.getMessages).mockResolvedValue({
      items: [{
        practice_turn_id: "practice-turn-old",
        turn_id: "TURN-01",
        prompt: "첫 번째 질문입니다.",
        user_answer: "첫 번째 답변입니다.",
        timed_out: false,
        dialogue_response: "이전 질문의 중개사 반응입니다.",
        created_at: "2026-07-23T00:00:01Z",
      }],
      next_cursor: null,
      has_more: false,
    });

    renderSession();

    expect(await screen.findByRole("heading", { name: "현재 두 번째 질문입니다." })).toBeInTheDocument();
    // 이전 TURN 반응은 대화 기록에는 남되 아바타 재생(heading)·입력 잠금은 되살리지 않는다.
    expect(screen.queryByRole("heading", { name: "이전 질문의 중개사 반응입니다." })).not.toBeInTheDocument();
    expect(screen.getByLabelText("내 답변")).toBeEnabled();
  });

  it("restores the initial prompt media when the session has no conversation yet", async () => {
    vi.spyOn(practiceService, "getSession").mockResolvedValue(session({
      current_state: "TURN-01",
      current_turn: dialogueTurn("TURN-01", "첫 번째 질문입니다."),
    }));
    vi.mocked(practiceService.getLatestMedia).mockResolvedValue({
      media_job_id: "media-intro",
      practice_turn_id: "practice-turn-intro",
      media_kind: "initial_prompt",
      status: "failed",
      provider: "local",
      speech_text: "첫 번째 질문입니다.",
      audio_url: null,
      video_url: null,
      error_code: "media_generation_failed",
      created_at: "2026-07-23T00:00:01Z",
      completed_at: "2026-07-23T00:00:02Z",
    });
    vi.mocked(practiceService.getMessages).mockResolvedValue({
      items: [],
      next_cursor: null,
      has_more: false,
    });

    renderSession();

    expect(await screen.findByRole("heading", { name: "첫 번째 질문입니다." })).toBeInTheDocument();
    expect(screen.getByLabelText("내 답변")).toBeDisabled();
    await waitFor(() => {
      expect(screen.getByTestId("practice-video")).toHaveAttribute("src", "/practice/avatar/speaking.mp4");
    });
    fireEvent.ended(screen.getByTestId("practice-video"));
    await waitFor(() => expect(screen.getByLabelText("내 답변")).toBeEnabled());
  });

  it("does not restore initial prompt media after the first turn", async () => {
    vi.spyOn(practiceService, "getSession").mockResolvedValue(session({
      current_state: "TURN-02",
      current_turn: dialogueTurn("TURN-02", "현재 두 번째 질문입니다."),
    }));
    vi.mocked(practiceService.getLatestMedia).mockResolvedValue({
      media_job_id: "media-intro-old",
      practice_turn_id: "practice-turn-intro",
      media_kind: "initial_prompt",
      status: "failed",
      provider: "local",
      speech_text: "오래된 첫 번째 질문입니다.",
      audio_url: null,
      video_url: null,
      error_code: "media_generation_failed",
      created_at: "2026-07-23T00:00:01Z",
      completed_at: "2026-07-23T00:00:02Z",
    });
    vi.mocked(practiceService.getMessages).mockResolvedValue({
      items: [],
      next_cursor: null,
      has_more: false,
    });

    renderSession();

    expect(await screen.findByRole("heading", { name: "현재 두 번째 질문입니다." })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "오래된 첫 번째 질문입니다." })).not.toBeInTheDocument();
    expect(screen.getByLabelText("내 답변")).toBeEnabled();
  });

  it("restores a reaction only when it belongs to the current turn", async () => {
    vi.spyOn(practiceService, "getSession").mockResolvedValue(session({
      current_state: "TURN-01",
      current_turn: dialogueTurn("TURN-01", "현재 질문입니다."),
    }));
    vi.mocked(practiceService.getLatestMedia).mockResolvedValue({
      media_job_id: "media-current",
      practice_turn_id: "practice-turn-current",
      media_kind: "dialogue_response",
      status: "failed",
      provider: "local",
      speech_text: "현재 질문에 대한 중개사 반응입니다.",
      audio_url: null,
      video_url: null,
      error_code: "media_generation_failed",
      created_at: "2026-07-23T00:00:01Z",
      completed_at: "2026-07-23T00:00:02Z",
    });
    vi.mocked(practiceService.getMessages).mockResolvedValue({
      items: [{
        practice_turn_id: "practice-turn-current",
        turn_id: "TURN-01",
        prompt: "현재 질문입니다.",
        user_answer: "조금 애매한 답변입니다.",
        timed_out: false,
        dialogue_response: "현재 질문에 대한 중개사 반응입니다.",
        created_at: "2026-07-23T00:00:01Z",
      }],
      next_cursor: null,
      has_more: false,
    });

    const view = renderSession();

    expect(await screen.findByRole("heading", { name: "현재 질문에 대한 중개사 반응입니다." })).toBeInTheDocument();
    expect(screen.getByLabelText("내 답변")).toBeDisabled();
    await screen.findByText("공인중개사가 말하고 있습니다");
    fireEvent.ended(view.getByTestId("practice-video"));
    expect(await screen.findByRole("heading", { name: "현재 질문입니다." })).toBeInTheDocument();
    expect(screen.getByLabelText("내 답변")).toBeEnabled();
  });

  it("logs each turn prompt once with the user answers and broker reactions", async () => {
    vi.spyOn(practiceService, "getSession").mockResolvedValue(session());
    vi.mocked(practiceService.getMessages).mockResolvedValue({
      items: [
        {
          practice_turn_id: "turn-001-attempt-1",
          turn_id: "TURN-01",
          prompt: "계약을 바로 진행하시겠습니까?",
          user_answer: "조건이 마음에 들지 않습니다.",
          timed_out: false,
          dialogue_response: "어떤 계약 내용을 물으시는지 말씀해 주세요.",
          created_at: "2026-07-23T00:00:01Z",
        },
        {
          practice_turn_id: "turn-001-attempt-2",
          turn_id: "TURN-01",
          prompt: "계약을 바로 진행하시겠습니까?",
          user_answer: "보증금 반환 시점을 묻는 겁니다.",
          timed_out: false,
          dialogue_response: "다음 세입자가 들어오면 반환한다고 들었습니다.",
          created_at: "2026-07-23T00:00:02Z",
        },
      ],
      next_cursor: null,
      has_more: false,
    });

    renderSession();
    fireEvent.click(await screen.findByText("이전 대화 보기"));
    const conversation = await screen.findByRole("tabpanel", { name: "지금까지의 대화" });

    // 이어서 답할 질문(prompt)은 같은 TURN 재시도에서 한 번만 남는다
    const openingPrompt = within(conversation).getByText("계약을 바로 진행하시겠습니까?");
    const firstAnswer = within(conversation).getByText("조건이 마음에 들지 않습니다.");
    expect(openingPrompt.compareDocumentPosition(firstAnswer) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(within(conversation).getAllByText("계약을 바로 진행하시겠습니까?")).toHaveLength(1);
    expect(within(conversation).getByText("보증금 반환 시점을 묻는 겁니다.")).toBeInTheDocument();
    // 답변마다 중개사 반응(dialogue_response)이 대화 기록에 남는다
    expect(within(conversation).getByText("어떤 계약 내용을 물으시는지 말씀해 주세요.")).toBeInTheDocument();
    expect(within(conversation).getByText("다음 세입자가 들어오면 반환한다고 들었습니다.")).toBeInTheDocument();
  });

  it("speaks the broker reaction and records it in conversation", async () => {
    vi.spyOn(practiceService, "getSession").mockResolvedValue(session());
    const next = session({ current_state: "TURN-02", current_turn: dialogueTurn("TURN-02", "권한 자료도 필요할까요?"), confirmed_action_ids: ["PA01"] });
    const submit = vi.spyOn(practiceService, "submitTurn").mockResolvedValue(turnResponse(next));
    renderSession();

    fireEvent.change(await screen.findByLabelText("내 답변"), { target: { value: " 자료를 확인하고 보류하겠습니다. " } });
    fireEvent.click(screen.getByRole("button", { name: "전송" }));

    await waitFor(() => expect(submit).toHaveBeenCalledWith("session-001", expect.objectContaining({
      turn_id: "TURN-01",
      user_answer: "자료를 확인하고 보류하겠습니다.",
      timed_out: false,
    })));
    // 아바타는 방금 답변에 대한 상대방 반응을 말한다.
    expect(await screen.findByRole("heading", { name: "확인 요청을 반영했습니다." })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "다음 상황으로" })).not.toBeInTheDocument();
    expect(screen.queryByText("이어서 확인할 내용")).toBeNull();
    expect(screen.queryByText(/확인 행동 \d+ \/ \d+/)).not.toBeInTheDocument();
    // 반응이 끝나기 전에는 다음 질문을 대화 기록에도 미리 띄우지 않는다.
    fireEvent.click(screen.getByText("이전 대화 보기"));
    expect(within(await screen.findByRole("tabpanel", { name: "지금까지의 대화" })).queryByText("권한 자료도 필요할까요?")).not.toBeInTheDocument();

    fireEvent.ended(screen.getByTestId("practice-video"));

    expect(await screen.findByText("자료를 확인하고 보류하겠습니다.")).toBeInTheDocument();
    // 대화 기록에는 답변한 TURN의 질문(prompt)과 중개사 반응(dialogue_response)이 함께 남는다
    const log = screen.getByRole("tabpanel", { name: "지금까지의 대화" });
    expect(within(log).getByText("계약을 바로 진행하시겠습니까?")).toBeInTheDocument();
    expect(within(log).getByText("확인 요청을 반영했습니다.")).toBeInTheDocument();
    expect(within(log).getByText("권한 자료도 필요할까요?")).toBeInTheDocument();
    expect(within(log).getAllByText("공인중개사")).toHaveLength(3);
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

  it("continues to the next prompt after no response without a stage button", async () => {
    vi.spyOn(practiceService, "getSession").mockResolvedValue(session());
    const next = session({
      current_state: "TURN-02",
      current_turn: dialogueTurn("TURN-02", "다음 확인 상황입니다."),
    });
    const submit = vi.spyOn(practiceService, "submitTurn").mockResolvedValue(turnResponse(next, "no_response"));
    renderSession();

    fireEvent.click(await screen.findByRole("button", { name: "답변하지 못했어요" }));

    await waitFor(() => expect(submit).toHaveBeenCalledWith("session-001", expect.objectContaining({
      turn_id: "TURN-01",
      user_answer: null,
      timed_out: true,
    })));
    expect(await screen.findByRole("heading", { name: "답변이 없으면 기존 특약 문구를 유지하겠습니다." })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "다음 상황으로" })).not.toBeInTheDocument();
    expect(screen.queryByText("이어서 확인할 내용")).toBeNull();
  });

  it.each([
    ["ambiguous_answer", "말씀하신 뜻이 분명하지 않은데, 앞서 안내드린 조건대로 진행해도 될까요?"],
    ["partial_check", "말씀하신 취지는 알겠지만, 그 부분은 나중에 확인하고 우선 진행하시죠."],
  ] as const)("records an in-role %s reaction and naturally continues", async (category, reaction) => {
    vi.spyOn(practiceService, "getSession").mockResolvedValue(session());
    const next = session({
      current_state: "TURN-02",
      current_turn: dialogueTurn("TURN-02", "다음 확인 상황입니다."),
    });
    vi.spyOn(practiceService, "submitTurn").mockResolvedValue(turnResponse(next, category));
    renderSession();

    fireEvent.change(await screen.findByLabelText("내 답변"), { target: { value: "잘 모르겠지만 계약 얘기인 것 같습니다." } });
    fireEvent.click(screen.getByRole("button", { name: "전송" }));

    // 반응을 재생하는 동안에는 다음 질문을 감추고 입력도 받지 않는다.
    expect(await screen.findByRole("heading", { name: reaction })).toBeInTheDocument();
    expect(screen.getByLabelText("내 답변")).toBeDisabled();
    expect(screen.queryByText("다음 확인 상황입니다.")).not.toBeInTheDocument();

    fireEvent.ended(screen.getByTestId("practice-video"));

    // 반응이 끝나면 다음 질문이 나오고 입력이 다시 열린다.
    expect(await screen.findByRole("heading", { name: "다음 확인 상황입니다." })).toBeInTheDocument();
    expect(screen.getByLabelText("내 답변")).toBeEnabled();
    expect(screen.queryByRole("button", { name: "다음 상황으로" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByText("이전 대화 보기"));
    expect(within(await screen.findByRole("tabpanel", { name: "지금까지의 대화" })).getByText(reaction)).toBeInTheDocument();
  });

  it("explains a provider review fallback and allows the same turn to be retried", async () => {
    vi.spyOn(practiceService, "getSession").mockResolvedValue(session());
    vi.spyOn(practiceService, "submitTurn").mockResolvedValue(turnResponse(session(), "needs_review"));
    renderSession();

    fireEvent.change(await screen.findByLabelText("내 답변"), { target: { value: "자료를 확인하겠습니다." } });
    fireEvent.click(screen.getByRole("button", { name: "전송" }));

    // provider 실패는 다음 TURN으로 진행하지 않으므로 현재 TURN의 fallback 대사를 유지한다.
    expect(await screen.findByRole("heading", { name: "계약을 바로 진행하시겠습니까?" })).toBeInTheDocument();
    expect(screen.queryByText("이어서 확인할 내용")).toBeNull();
    fireEvent.click(screen.getByText("이전 대화 보기"));
    const conversation = await screen.findByRole("tabpanel", { name: "지금까지의 대화" });
    expect(within(conversation).getAllByText("계약을 바로 진행하시겠습니까?")).toHaveLength(1);
    expect(within(conversation).getByText("답변을 다시 말씀해 주세요.")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent(
      "답변을 확인하지 못했습니다. 입력한 내용은 잘못된 답변으로 처리하지 않았습니다. 연습은 계속할 수 있습니다.",
    );
    expect(screen.getByRole("button", { name: "다시 확인하기" })).toHaveClass("secondary");
    expect(screen.getByRole("button", { name: "대화를 계속하기" })).toHaveClass("secondary");
    expect(document.body).not.toHaveTextContent("provider_timeout");
    expect(document.body).not.toHaveTextContent("case_id");
    const retryAnswer = screen.getByLabelText("내 답변");
    expect(retryAnswer).toBeDisabled();
    fireEvent.ended(screen.getByTestId("practice-video"));
    expect(retryAnswer).toBeEnabled();
    expect(retryAnswer).toHaveValue("");
    fireEvent.change(retryAnswer, { target: { value: "같은 내용을 다시 확인하겠습니다." } });
    expect(screen.getByRole("button", { name: "전송" })).toBeEnabled();
  });

  it("treats a response validation failure as a non-answer fallback", async () => {
    vi.spyOn(practiceService, "getSession").mockResolvedValue(session());
    const invalidResponse = turnResponse(session(), "needs_review");
    invalidResponse.evaluation!.fallback_reason = "response_validation_failed";
    vi.spyOn(practiceService, "submitTurn").mockResolvedValue(invalidResponse);
    renderSession();

    fireEvent.change(await screen.findByLabelText("내 답변"), { target: { value: "자료를 확인하겠습니다." } });
    fireEvent.click(screen.getByRole("button", { name: "전송" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "답변을 확인하지 못했습니다. 입력한 내용은 잘못된 답변으로 처리하지 않았습니다. 연습은 계속할 수 있습니다.",
    );
    expect(screen.getByRole("button", { name: "다시 확인하기" })).toBeVisible();
    expect(screen.getByLabelText("내 답변")).toBeDisabled();
    fireEvent.ended(screen.getByTestId("practice-video"));
    expect(screen.getByLabelText("내 답변")).toBeEnabled();
  });

  it("preserves the typed answer after a network error", async () => {
    vi.spyOn(practiceService, "getSession").mockResolvedValue(session());
    vi.spyOn(practiceService, "submitTurn").mockRejectedValue(new Error("네트워크 연결을 확인해 주세요."));
    renderSession();

    const answer = await screen.findByLabelText("내 답변");
    fireEvent.change(answer, { target: { value: "권한 자료를 확인하겠습니다." } });
    fireEvent.click(screen.getByRole("button", { name: "전송" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("답변을 보내지 못했습니다. 입력한 답변은 그대로 남아 있습니다. 다시 시도해 주세요.");
    expect(answer).toHaveValue("권한 자료를 확인하겠습니다.");
    expect(screen.getByRole("button", { name: "전송" })).toBeEnabled();
  });

  it("asks for the final contract decision and can restart the scenario", async () => {
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

    const finalSection = (await screen.findByRole("heading", { name: "마지막 행동을 선택해 주세요" })).closest("section")!;
    expect(within(finalSection).getAllByRole("button").map((button) => button.textContent)).toEqual([
      "계약을 진행하겠습니다",
      "계약 전에 추가로 확인하겠습니다",
      "오늘은 계약을 보류하겠습니다",
      "계약을 중단하겠습니다",
      "처음부터 다시 연습하기",
    ]);
    fireEvent.click(within(finalSection).getByRole("button", { name: "계약을 진행하겠습니다" }));

    await waitFor(() => expect(submit).toHaveBeenCalledWith("session-001", expect.objectContaining({ selected_action: "진행" })));
    expect(await screen.findByText("결과 화면 이동 완료")).toBeInTheDocument();
  });

  it("finishes the last broker reaction before showing final action choices", async () => {
    vi.spyOn(practiceService, "getSession").mockResolvedValue(
      session({ current_state: "TURN-03", current_turn: dialogueTurn("TURN-03", "오늘 서명하시겠어요?") }),
    );
    const actionSession = session({ current_state: "ACTION-SELECTION", current_turn: null });
    vi.spyOn(practiceService, "submitTurn").mockResolvedValue(
      turnResponse(actionSession, "appropriate_check"),
    );
    renderSession();

    fireEvent.change(await screen.findByLabelText("내 답변"), { target: { value: "확인 전에는 서명하지 않겠습니다." } });
    fireEvent.click(screen.getByRole("button", { name: "전송" }));

    expect(await screen.findByRole("heading", { name: "확인 요청을 반영했습니다." })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "마지막 행동을 선택해 주세요" })).not.toBeInTheDocument();
    expect(screen.getByLabelText("내 답변")).toBeDisabled();

    fireEvent.ended(screen.getByTestId("practice-video"));

    expect(await screen.findByRole("heading", { name: "마지막 행동을 선택해 주세요" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "확인 요청을 반영했습니다." })).not.toBeInTheDocument();
  });

  it("asks the user to confirm a contract decision read from the answer before ending", async () => {
    vi.spyOn(practiceService, "getSession").mockResolvedValue(session());
    const next = session({ current_state: "TURN-02", current_turn: dialogueTurn("TURN-02", "다음 확인 상황입니다.") });
    vi.spyOn(practiceService, "submitTurn").mockResolvedValue(turnResponse(next, "appropriate_check", "중단"));
    const advance = vi.spyOn(practiceService, "advanceDialogue").mockResolvedValue(turnResponse(next));
    const submitFinal = vi.spyOn(practiceService, "submitFinalAction").mockResolvedValue(turnResponse(next));
    renderSession();

    fireEvent.change(await screen.findByLabelText("내 답변"), { target: { value: "오늘은 계약하지 않겠습니다." } });
    fireEvent.click(screen.getByRole("button", { name: "전송" }));

    // 반응을 재생하는 동안에는 확인 화면을 띄우지 않는다.
    await screen.findByRole("heading", { name: "확인 요청을 반영했습니다." });
    expect(screen.queryByRole("heading", { name: "계약을 중단하시겠습니까?" })).not.toBeInTheDocument();

    fireEvent.ended(screen.getByTestId("practice-video"));

    // 의도만으로 끝내지 않고 사용자가 직접 확인해야 최종 선택으로 확정된다.
    expect(await screen.findByRole("heading", { name: "계약을 중단하시겠습니까?" })).toBeInTheDocument();
    expect(screen.getByLabelText("내 답변")).toBeDisabled();
    expect(submitFinal).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "네, 이렇게 하겠습니다" }));

    // 종료로 넘어갈 때는 세션이 지금 머무는 장면을 기준으로 최종 선택 단계로 이동한다.
    await waitFor(() => expect(advance).toHaveBeenCalledWith("session-001", expect.objectContaining({
      turn_id: "TURN-02",
      destination: "action_selection",
    })));
    await waitFor(() => expect(submitFinal).toHaveBeenCalledWith("session-001", expect.objectContaining({
      selected_action: "중단",
    })));
    expect(await screen.findByText("결과 화면 이동 완료")).toBeInTheDocument();
  });

  it("keeps the conversation going when the user declines the confirmation", async () => {
    vi.spyOn(practiceService, "getSession").mockResolvedValue(session());
    const next = session({ current_state: "TURN-02", current_turn: dialogueTurn("TURN-02", "다음 확인 상황입니다.") });
    vi.spyOn(practiceService, "submitTurn").mockResolvedValue(turnResponse(next, "appropriate_check", "보류"));
    const submitFinal = vi.spyOn(practiceService, "submitFinalAction");
    renderSession();

    fireEvent.change(await screen.findByLabelText("내 답변"), { target: { value: "일단 보류하고 싶어요." } });
    fireEvent.click(screen.getByRole("button", { name: "전송" }));
    fireEvent.ended(await screen.findByTestId("practice-video"));

    fireEvent.click(await screen.findByRole("button", { name: "아니요, 대화를 더 하겠습니다" }));

    expect(screen.queryByRole("heading", { name: "오늘은 계약을 보류하시겠습니까?" })).not.toBeInTheDocument();
    expect(screen.getByLabelText("내 답변")).toBeEnabled();
    expect(submitFinal).not.toHaveBeenCalled();
  });

  it("does not ask to end for intents that continue the conversation", async () => {
    vi.spyOn(practiceService, "getSession").mockResolvedValue(session());
    const next = session({ current_state: "TURN-02", current_turn: dialogueTurn("TURN-02", "다음 확인 상황입니다.") });
    vi.spyOn(practiceService, "submitTurn").mockResolvedValue(turnResponse(next, "appropriate_check", "특약 수정 요구"));
    renderSession();

    fireEvent.change(await screen.findByLabelText("내 답변"), { target: { value: "특약을 고쳐 주면 계약할게요." } });
    fireEvent.click(screen.getByRole("button", { name: "전송" }));
    fireEvent.ended(await screen.findByTestId("practice-video"));

    expect(await screen.findByRole("heading", { name: "다음 확인 상황입니다." })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /하시겠습니까\?$/ })).not.toBeInTheDocument();
    expect(screen.getByLabelText("내 답변")).toBeEnabled();
  });

  it("starts a new session when the user retries the scenario", async () => {
    vi.spyOn(practiceService, "getSession").mockResolvedValue(
      session({ current_state: "ACTION-SELECTION", current_turn: null }),
    );
    const create = vi.spyOn(practiceService, "createSession").mockResolvedValue(
      session({ practice_session_id: "session-002" }),
    );
    renderSession();

    fireEvent.click(await screen.findByRole("button", { name: "처음부터 다시 연습하기" }));

    await waitFor(() => expect(create).toHaveBeenCalledWith("PRACTICE-DEFERRED-REFUND-001"));
  });

  it("moves to the next situation after a provider fallback without recording an answer", async () => {
    vi.spyOn(practiceService, "getSession").mockResolvedValue(session());
    vi.spyOn(practiceService, "submitTurn").mockResolvedValue(turnResponse(session(), "needs_review"));
    const advance = vi.spyOn(practiceService, "advanceDialogue").mockResolvedValue(
      turnResponse(session({ current_state: "TURN-02", current_turn: dialogueTurn("TURN-02", "다음 확인 상황입니다.") })),
    );
    renderSession();

    fireEvent.change(await screen.findByLabelText("내 답변"), { target: { value: "자료를 확인하겠습니다." } });
    fireEvent.click(screen.getByRole("button", { name: "전송" }));
    const continueButton = await screen.findByRole("button", { name: "대화를 계속하기" });
    expect(continueButton).toBeDisabled();
    fireEvent.ended(screen.getByTestId("practice-video"));
    fireEvent.click(await screen.findByRole("button", { name: "대화를 계속하기" }));

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
      ending_type: "transaction_stopped",
      ending_title: "⚠️ 진행 중단 엔딩",
      feedback_label: "잘한 점과 보완할 점",
      feedback: "확인되지 않은 조건에서 계약 진행을 멈췄습니다.",
      practice_phrase: "수정된 특약을 확인하기 전에는 계약을 진행하지 않겠습니다.",
      action_summary: [
        "확인되지 않은 계약을 중단한다.",
        "필요한 수정 문구를 제시한다.",
        "확인 전에는 계약금을 보내지 않는다.",
      ],
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

    expect(await screen.findByRole("heading", { name: "⚠️ 진행 중단 엔딩" })).toBeInTheDocument();
    // 내가 고른 행동과 확인 정도를 서로 다른 축으로 나란히 보여 준다.
    const outcome = screen.getByRole("heading", { name: "내가 선택한 행동과 확인한 내용" }).parentElement!;
    expect(within(outcome).getByText("보류")).toBeInTheDocument();
    expect(within(outcome).getByText("1개 / 전체 2개")).toBeInTheDocument();
    expect(within(outcome).getByText("1개")).toBeInTheDocument();
    expect(within(outcome).getByText("반환 조건을 확인함")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "잘한 점과 보완할 점" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "실제로 이렇게 말해보세요" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "행동 지침 3줄 요약" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "추가로 조심해야 할 부분" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "다른 표현 예시" })).toBeInTheDocument();
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
