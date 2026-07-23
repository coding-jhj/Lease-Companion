import { http, HttpResponse } from "msw";
import type {
  PracticeAnswerCategory,
  PracticeDialogueTurnDto,
  PracticeResultDto,
  PracticeScenarioDetailDto,
  PracticeSelectedAction,
  PracticeSessionDto,
  PracticeSyntheticContractDto,
  PracticeTurnEvaluationDto,
  PracticeTurnResponseDto,
} from "../types/api";

interface MockScenario extends PracticeScenarioDetailDto {
  turns: PracticeDialogueTurnDto[];
  targetActions: string[];
  missedSignals: string[];
  recommendedPhrases: string[];
  nextActions: string[];
  officialSourceIds: string[];
}

interface MockSession {
  response: PracticeSessionDto;
  turnIndex: number;
  result: PracticeResultDto | null;
  requestIds: Set<string>;
}

const now = "2026-07-22T00:00:00Z";
const labels = ["가상 연습", "합성 시나리오"];
const finalActions: PracticeSelectedAction[] = ["진행", "추가 확인", "보류", "중단"];

function contract(overrides: Partial<PracticeSyntheticContractDto>): PracticeSyntheticContractDto {
  return {
    contract_type: "전세",
    signed: false,
    deposit_paid: false,
    property_address: "서울특별시 가온구 새봄로 18, 202동 703호",
    deposit: 180000000,
    monthly_rent: null,
    contract_payment: 18000000,
    balance_payment: 162000000,
    requested_provisional_payment: 0,
    contract_payment_date: "2026-07-25",
    balance_payment_date: "2026-08-31",
    move_in_date: "2026-08-31",
    start_date: "2026-08-31",
    end_date: "2028-08-30",
    landlord_name: "한도윤",
    broker_name: "오가람",
    is_proxy_contract: false,
    agent_name: null,
    agent_relationship: null,
    proxy_authority_documents: [],
    account_holder: "한도윤",
    account_number_stored: false,
    registry_issue_date: "2026-07-22",
    registry_property_address: "서울특별시 가온구 새봄로 18, 202동 703호",
    owner_names: ["한도윤"],
    is_joint_ownership: false,
    owner_shares: { 한도윤: "1/1" },
    mortgage_present: false,
    mortgage_maximum_claim: null,
    deposit_return_clause: "임대차 종료일에 보증금을 반환한다.",
    rights_change_clause_present: true,
    special_clauses: [],
    ...overrides,
  };
}

function turn(turnId: string, prompt: string, pressured = false): PracticeDialogueTurnDto {
  return {
    turn_id: turnId,
    prompt,
    wait_sequence: pressured ? [
      { state: "WAIT_BASIC", from_second: 0, to_second: 5, line: null },
      { state: "WAIT_PRESSURE", from_second: 5, to_second: 10, line: null },
      { state: "PRESSURE_REMINDER", from_second: 10, to_second: null, line: "지금 결정하지 않으면 다른 분에게 넘어갈 수 있습니다." },
    ] : [],
  };
}

const scenarios: MockScenario[] = [
  {
    scenario_id: "PRACTICE-DEFERRED-REFUND-001",
    scenario_version: "1.1.0",
    title: "후임 임차인 조건부 보증금 반환",
    role: "공인중개사",
    difficulty: "기본",
    contract_stage: "서명 전",
    always_show_labels: labels,
    synthetic_contract: contract({
      deposit_return_clause: "임대인은 신규 임차인의 입주 및 보증금 수령이 완료된 후 임차인에게 임대차보증금을 반환한다.",
      special_clauses: [
        "임차인은 계약 종료 시 임차목적물을 원상회복하여 임대인에게 인도한다. 다만, 통상적인 사용으로 인한 마모 및 노후는 제외한다.",
        "임대인은 신규 임차인의 입주 및 보증금 수령이 완료된 후 임차인에게 임대차보증금을 반환한다.",
        "임대인은 잔금 지급일 다음 날까지 본 목적물에 근저당권 등 새로운 권리를 설정하지 아니한다.",
      ],
    }),
    initial_turn: turn("TURN-01", "임대인분은 특약대로 다음 세입자가 들어오면 보증금을 바로 반환하겠다고 하십니다. 이 조건으로 진행해도 괜찮으시죠?", true),
    turns: [
      turn("TURN-01", "임대인분은 특약대로 다음 세입자가 들어오면 보증금을 바로 반환하겠다고 하십니다. 이 조건으로 진행해도 괜찮으시죠?", true),
      turn("TURN-02", "임대인분 말씀으로는 새 세입자는 금방 구해질 테니 걱정하지 않으셔도 된다고 합니다. 구두로도 확실히 약속하셨습니다."),
      turn("TURN-03", "임대인분이 특약은 나중에도 협의할 수 있다고 하십니다. 우선 오늘 계약서에 서명하시죠."),
    ],
    targetActions: ["후임 임차인 조건부 반환 구조 확인", "구두 설명 대신 반환 특약 수정 요구", "특약 수정 확인 전 계약 진행 보류"],
    missedSignals: ["보증금 반환이 신규 임차인의 입주에 연동된 조건"],
    recommendedPhrases: ["신규 임차인 입주와 관계없이 계약 종료 시 보증금을 반환하도록 특약을 수정해 주세요."],
    nextActions: ["수정된 특약 원문을 확인하기 전에는 서명하지 않습니다."],
    officialSourceIds: ["SRC-HTA-LAW", "SRC-STD-LEASE"],
  },
  {
    scenario_id: "PRACTICE-THIRD-PARTY-PAYMENT-001",
    scenario_version: "1.1.0",
    title: "공인중개사 명의 계좌로 가계약금 송금 요구",
    role: "공인중개사",
    difficulty: "기본",
    contract_stage: "가계약금 입금 전",
    always_show_labels: labels,
    synthetic_contract: contract({
      property_address: "서울특별시 가온구 다솜로 18, 102동 703호",
      registry_property_address: "서울특별시 가온구 다솜로 18, 102동 703호",
      deposit: 230000000,
      contract_payment: 23000000,
      balance_payment: 207000000,
      requested_provisional_payment: 1000000,
      landlord_name: "박서연",
      broker_name: "이도윤",
      account_holder: "이도윤",
      owner_names: ["박서연"],
      owner_shares: { 박서연: "1/1" },
      special_clauses: [
        "본 계약은 현 시설 상태에서 체결하며, 임차인은 계약 전 목적물의 시설 상태를 확인한다.",
        "계약금 및 잔금은 임대인이 지정한 계좌로 지급하고, 임대인은 지급받은 금액에 대한 영수증을 교부한다.",
        "임대인은 계약 체결일부터 잔금 지급일 다음 날까지 본 목적물에 근저당권 등 새로운 권리를 설정하지 아니한다.",
      ],
    }),
    initial_turn: turn("TURN-01", "임대인께서 바쁘셔서 제 명의 계좌로 가계약금 100만 원을 받기로 했습니다. 바로 보내 주시겠어요?"),
    turns: [
      turn("TURN-01", "임대인께서 바쁘셔서 제 명의 계좌로 가계약금 100만 원을 받기로 했습니다. 바로 보내 주시겠어요?"),
      turn("TURN-02", "중개사 계좌로 받는 경우도 많고 제가 영수증을 드리면 됩니다. 별도 서류까지 필요할까요?"),
      turn("TURN-03", "다른 분도 계약하려고 해서 지금 100만 원을 보내야 집을 잡아 둘 수 있습니다. 확인 자료는 송금 뒤에 드리겠습니다.", true),
    ],
    targetActions: ["입금 명의와 계약 상대 불일치 확인", "제3자 수령 관계와 권한 자료 확인", "확인 완료 전 가계약금 송금 보류"],
    missedSignals: ["입금 계좌 명의가 임대인·등기상 소유자와 다름", "제3자의 수령 권한 자료가 제시되지 않음"],
    recommendedPhrases: ["임대인과 계좌 명의의 관계 및 수령 권한 자료를 확인하기 전에는 송금하지 않겠습니다."],
    nextActions: ["임대인 본인 명의 계좌 또는 적법한 수령 권한 자료를 확인합니다."],
    officialSourceIds: ["SRC-STD-LEASE", "SRC-MOLIT-CHECKLIST"],
  },
  {
    scenario_id: "PRACTICE-PROXY-AUTHORITY-001",
    scenario_version: "1.1.0",
    title: "대리인 권한 자료 없는 계약 요구",
    role: "공인중개사",
    difficulty: "기본",
    contract_stage: "계약서 서명·계약금 입금 전",
    always_show_labels: labels,
    synthetic_contract: contract({
      property_address: "서울특별시 가온구 다온로 18, 102동 503호",
      registry_property_address: "서울특별시 가온구 다온로 18, 102동 503호",
      deposit: 210000000,
      contract_payment: 21000000,
      balance_payment: 189000000,
      requested_provisional_payment: 1000000,
      landlord_name: "한서윤",
      broker_name: "오지민",
      account_holder: "박민준",
      owner_names: ["한서윤"],
      owner_shares: { 한서윤: "1/1" },
      is_proxy_contract: true,
      agent_name: "박민준",
      agent_relationship: "임대인의 친족",
      special_clauses: [
        "본 계약은 현 시설 상태에서 체결하며, 임차인은 계약 전 목적물의 시설 상태를 확인한다.",
        "본 계약의 체결 및 계약금 수령에 관한 절차는 임대인이 지정한 대리인 박민준을 통하여 진행한다.",
        "임차인은 임대인의 사전 동의 없이 임차권을 양도하거나 본 목적물을 전대하지 아니한다.",
      ],
    }),
    initial_turn: turn("TURN-01", "등기상 소유자분은 오늘 못 오시고 친족인 박민준 씨가 대신 계약합니다. 가족이니 바로 진행해도 되겠죠?", true),
    turns: [
      turn("TURN-01", "등기상 소유자분은 오늘 못 오시고 친족인 박민준 씨가 대신 계약합니다. 가족이니 바로 진행해도 되겠죠?", true),
      turn("TURN-02", "위임장과 인감증명서는 계약 후에 보내드릴 수 있습니다. 대리인 신분증만 확인하고 서명하시죠."),
      turn("TURN-03", "집을 잡으려면 지금 대리인 박민준 씨와 계약서에 서명하고 그분 계좌로 계약금을 보내셔야 합니다. 서류는 뒤에 보완하겠습니다."),
    ],
    targetActions: ["등기상 소유자와 계약 상대 확인", "대리인 권한 서류와 권한 범위 확인", "권한 확인 전 서명·송금 보류"],
    missedSignals: ["대리 계약이지만 권한 자료와 위임 범위가 제시되지 않음"],
    recommendedPhrases: ["위임장과 인감증명서, 계약 및 계약금 수령 권한 범위를 확인하기 전에는 서명하거나 송금하지 않겠습니다."],
    nextActions: ["등기상 소유자에게 대리 권한과 계약 의사를 별도로 확인합니다."],
    officialSourceIds: ["SRC-MOLIT-CHECKLIST", "SRC-STD-LEASE"],
  },
];

const sessions = new Map<string, MockSession>();
const sessionStoragePrefix = "lease-companion:practice-session:";

function getStoredSession(id: string): MockSession | undefined {
  const existing = sessions.get(id);
  if (existing) return existing;
  try {
    const stored = globalThis.localStorage?.getItem(`${sessionStoragePrefix}${id}`);
    if (!stored) return undefined;
    const parsed = JSON.parse(stored) as Omit<MockSession, "requestIds"> & { requestIds: string[] };
    const restored = { ...parsed, requestIds: new Set(parsed.requestIds) };
    sessions.set(id, restored);
    return restored;
  } catch {
    return undefined;
  }
}

function storeSession(id: string, session: MockSession) {
  sessions.set(id, session);
  try {
    globalThis.localStorage?.setItem(`${sessionStoragePrefix}${id}`, JSON.stringify({
      ...session,
      requestIds: [...session.requestIds],
    }));
  } catch {
    // Node 기반 단위 테스트처럼 브라우저 저장소가 없는 환경에서는 메모리 상태만 사용한다.
  }
}

function findScenario(id: string) {
  return scenarios.find((scenario) => scenario.scenario_id === id);
}

function publicScenario(scenario: MockScenario): PracticeScenarioDetailDto {
  const { turns: _turns, targetActions: _targetActions, missedSignals: _missedSignals, recommendedPhrases: _recommendedPhrases, nextActions: _nextActions, officialSourceIds: _officialSourceIds, ...detail } = scenario;
  return detail;
}

function error(code: string, message: string, status: number) {
  return HttpResponse.json({ error: { code, message } }, { status });
}

function evaluate(turnId: string, answer: string | null, timedOut: boolean, actionId: string): PracticeTurnEvaluationDto {
  const category: PracticeAnswerCategory = timedOut
    ? "no_response"
    : /확인|요청|수정|고쳐|보류|송금하지|서명하지/.test(answer ?? "")
      ? "appropriate_check"
      : "partial_check";
  return {
    schema_version: "1.9.0",
    turn_id: turnId,
    answer_category: category,
    confirmed_action_ids: category === "appropriate_check" ? [actionId] : [],
    next_dialogue_state: timedOut ? turnId : "next",
    fallback_reason: null,
    evidence_text: category === "appropriate_check" ? answer : null,
    verbal_reliance: "not_observed",
  };
}

export const practiceHandlers = [
  http.get("/api/practice-scenarios", () => HttpResponse.json(scenarios.map(({ synthetic_contract: _contract, initial_turn: _initialTurn, turns: _turns, targetActions: _targetActions, missedSignals: _missedSignals, recommendedPhrases: _recommendedPhrases, nextActions: _nextActions, officialSourceIds: _officialSourceIds, ...summary }) => summary))),
  http.get("/api/practice-scenarios/:scenarioId", ({ params }) => {
    const scenario = findScenario(String(params.scenarioId));
    return scenario ? HttpResponse.json(publicScenario(scenario)) : error("practice_scenario_not_found", "승인된 연습 시나리오를 찾을 수 없습니다.", 404);
  }),
  http.post("/api/practice-sessions", async ({ request }) => {
    const body = (await request.json()) as { scenario_id: string };
    const scenario = findScenario(body.scenario_id);
    if (!scenario) return error("practice_scenario_not_found", "승인된 연습 시나리오를 찾을 수 없습니다.", 404);
    const id = crypto.randomUUID().replaceAll("-", "");
    const response: PracticeSessionDto = {
      practice_session_id: id,
      scenario_id: scenario.scenario_id,
      scenario_version: scenario.scenario_version,
      status: "active",
      current_state: scenario.turns[0].turn_id,
      current_turn: scenario.turns[0],
      confirmed_action_ids: [],
      selected_action: null,
      allowed_final_actions: finalActions,
      started_at: now,
      completed_at: null,
    };
    storeSession(id, { response, turnIndex: 0, result: null, requestIds: new Set() });
    return HttpResponse.json(response, { status: 201 });
  }),
  http.get("/api/practice-sessions/:sessionId", ({ params }) => {
    const session = getStoredSession(String(params.sessionId));
    return session ? HttpResponse.json(session.response) : error("practice_session_not_found", "연습 세션을 찾을 수 없습니다.", 404);
  }),
  http.post("/api/practice-sessions/:sessionId/turns", async ({ params, request }) => {
    const sessionId = String(params.sessionId);
    const session = getStoredSession(sessionId);
    if (!session) return error("practice_session_not_found", "연습 세션을 찾을 수 없습니다.", 404);
    const body = (await request.json()) as { request_id: string; turn_id: string; user_answer: string | null; timed_out: boolean };
    if (session.requestIds.has(body.request_id)) return error("duplicate_practice_request", "이미 처리된 연습 요청입니다.", 409);
    if (session.response.current_turn?.turn_id !== body.turn_id) return error("invalid_practice_transition", "현재 대화 턴과 요청이 일치하지 않습니다.", 409);
    session.requestIds.add(body.request_id);
    const scenario = findScenario(session.response.scenario_id)!;
    const actionId = `PA${String(session.turnIndex + 1).padStart(2, "0")}`;
    const evaluation = evaluate(body.turn_id, body.user_answer, body.timed_out, actionId);
    if (!body.timed_out) session.turnIndex += 1;
    if (evaluation.confirmed_action_ids.length > 0) session.response.confirmed_action_ids.push(actionId);
    const nextTurn = scenario.turns[session.turnIndex] ?? null;
    session.response = {
      ...session.response,
      current_state: nextTurn?.turn_id ?? "ACTION-SELECTION",
      current_turn: nextTurn,
    };
    const response: PracticeTurnResponseDto = {
      practice_turn_id: crypto.randomUUID().replaceAll("-", ""),
      attempt_no: 1,
      evaluation,
      dialogue_response: body.timed_out ? "답변을 기다리고 있습니다. 같은 상황에서 다시 말해 보세요." : "말씀하신 확인 내용을 반영했습니다. 다음 상황으로 넘어가겠습니다.",
      session: session.response,
    };
    storeSession(sessionId, session);
    return HttpResponse.json(response);
  }),
  http.post("/api/practice-sessions/:sessionId/advance", async ({ params, request }) => {
    const sessionId = String(params.sessionId);
    const session = getStoredSession(sessionId);
    if (!session) return error("practice_session_not_found", "연습 세션을 찾을 수 없습니다.", 404);
    const body = (await request.json()) as {
      request_id: string;
      turn_id: string;
      destination: "next_turn" | "action_selection";
    };
    if (session.requestIds.has(body.request_id)) return error("duplicate_practice_request", "이미 처리된 연습 요청입니다.", 409);
    if (session.response.status !== "active" || session.response.current_turn?.turn_id !== body.turn_id) {
      return error("invalid_practice_transition", "현재 대화 턴과 요청이 일치하지 않습니다.", 409);
    }
    session.requestIds.add(body.request_id);
    const scenario = findScenario(session.response.scenario_id)!;
    const currentIndex = scenario.turns.findIndex((item) => item.turn_id === body.turn_id);
    const nextTurn = body.destination === "action_selection"
      ? null
      : scenario.turns[currentIndex + 1] ?? null;
    session.turnIndex = nextTurn ? currentIndex + 1 : scenario.turns.length;
    session.response = {
      ...session.response,
      current_state: nextTurn?.turn_id ?? "ACTION-SELECTION",
      current_turn: nextTurn,
    };
    storeSession(sessionId, session);
    return HttpResponse.json({
      practice_turn_id: crypto.randomUUID().replaceAll("-", ""),
      attempt_no: 1,
      evaluation: null,
      dialogue_response: null,
      session: session.response,
    } satisfies PracticeTurnResponseDto);
  }),
  http.post("/api/practice-sessions/:sessionId/final-action", async ({ params, request }) => {
    const sessionId = String(params.sessionId);
    const session = getStoredSession(sessionId);
    if (!session) return error("practice_session_not_found", "연습 세션을 찾을 수 없습니다.", 404);
    const body = (await request.json()) as { request_id: string; selected_action: PracticeSelectedAction };
    if (session.response.current_state !== "ACTION-SELECTION" || !finalActions.includes(body.selected_action)) return error("invalid_practice_transition", "현재 선택할 수 없는 최종 행동입니다.", 409);
    const scenario = findScenario(session.response.scenario_id)!;
    const confirmedNames = scenario.targetActions.filter((_, index) => session.response.confirmed_action_ids.includes(`PA${String(index + 1).padStart(2, "0")}`));
    session.response = { ...session.response, status: "completed", current_state: "DEBRIEF", current_turn: null, selected_action: body.selected_action, completed_at: now };
    session.result = {
      schema_version: "1.9.0",
      session_id: session.response.practice_session_id,
      scenario_id: scenario.scenario_id,
      scenario_version: scenario.scenario_version,
      selected_action: body.selected_action,
      confirmed_action_ids: session.response.confirmed_action_ids,
      missed_action_ids: scenario.targetActions.map((_, index) => `PA${String(index + 1).padStart(2, "0")}`).filter((id) => !session.response.confirmed_action_ids.includes(id)),
      confirmed_actions: confirmedNames,
      missed_signals: confirmedNames.length === scenario.targetActions.length ? [] : scenario.missedSignals,
      recommended_phrases: scenario.recommendedPhrases,
      next_actions: scenario.nextActions,
      official_source_ids: scenario.officialSourceIds,
    };
    storeSession(sessionId, session);
    return HttpResponse.json({ practice_turn_id: crypto.randomUUID().replaceAll("-", ""), attempt_no: 1, evaluation: null, dialogue_response: null, session: session.response } satisfies PracticeTurnResponseDto);
  }),
  http.get("/api/practice-sessions/:sessionId/result", ({ params }) => {
    const session = getStoredSession(String(params.sessionId));
    if (!session) return error("practice_session_not_found", "연습 세션을 찾을 수 없습니다.", 404);
    return session.result ? HttpResponse.json({ result: session.result }) : error("practice_result_not_ready", "아직 연습 결과가 생성되지 않았습니다.", 409);
  }),
];
