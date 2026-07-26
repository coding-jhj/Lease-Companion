import { FormEvent, KeyboardEvent, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ErrorState, LoadingState } from "../../components/feedback/AsyncState";
import { PageShell } from "../../components/layout/PageShell";
import { createPracticeRequestId, practiceService } from "../../services/practiceService";
import { PracticeAvatarStage } from "./PracticeAvatarStage";
import { PracticeChatPanel } from "./PracticeChatPanel";
import type {
  PracticeScenarioDetailDto,
  PracticeSessionDto,
  PracticeConversationTurnDto,
  PracticeMediaJobDto,
  PracticeSelectedAction,
  PracticeTurnResponseDto,
} from "../../types/api";

const money = new Intl.NumberFormat("ko-KR");

// 데스크탑(2단)에서는 이전 대화를 기본으로 펼쳐 두고, 모바일(오버레이)에서는 접어 둔다.
function isWideViewport() {
  return typeof window !== "undefined" && Boolean(window.matchMedia?.("(min-width: 900px)").matches);
}

function elapsedSeconds(startedAt: number) {
  return Math.min(3600, Math.max(0, (Date.now() - startedAt) / 1000));
}

interface SpeechRecognitionResultLike {
  readonly isFinal: boolean;
  readonly length: number;
  readonly [index: number]: { readonly transcript: string };
}

interface SpeechRecognitionEventLike {
  readonly results: ArrayLike<SpeechRecognitionResultLike>;
}

interface SpeechRecognitionErrorEventLike {
  readonly error: string;
}

interface SpeechRecognitionLike {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onerror: ((event: SpeechRecognitionErrorEventLike) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
}

type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;

function getSpeechRecognitionConstructor(): SpeechRecognitionConstructor | null {
  const speechWindow = window as typeof window & {
    SpeechRecognition?: SpeechRecognitionConstructor;
    webkitSpeechRecognition?: SpeechRecognitionConstructor;
  };
  return speechWindow.SpeechRecognition ?? speechWindow.webkitSpeechRecognition ?? null;
}

function speechRecognitionErrorMessage(error: string) {
  if (error === "not-allowed" || error === "service-not-allowed") {
    return "마이크 권한이 필요합니다. 브라우저 권한을 허용하거나 텍스트로 입력해 주세요.";
  }
  if (error === "no-speech") return "음성이 들리지 않았습니다. 다시 말하거나 텍스트로 입력해 주세요.";
  if (error === "audio-capture") return "마이크를 사용할 수 없습니다. 연결 상태를 확인해 주세요.";
  return "음성 입력을 완료하지 못했습니다. 다시 시도하거나 텍스트로 입력해 주세요.";
}

function practiceEvaluationNotice(response: PracticeTurnResponseDto | null) {
  const reason = response?.evaluation?.fallback_reason;
  return reason === "provider_error" || reason === "provider_timeout" || reason === "response_validation_failed"
    ? "답변을 확인하지 못했습니다. 입력한 내용은 잘못된 답변으로 처리하지 않았습니다. 연습은 계속할 수 있습니다."
    : null;
}

function ContractReference({ scenario }: {
  scenario: PracticeScenarioDetailDto;
}) {
  const contract = scenario.synthetic_contract;
  return (
      <section className="practice-contract-card practice-drawer-contract" role="tabpanel" aria-labelledby="drawer-tab-contract">
        <h2 id="practice-contract-reference-title">계약 내용</h2>
        <dl className="practice-drawer-facts">
          <div><dt>계약 유형</dt><dd>{contract.contract_type}</dd></div>
          <div><dt>주택 주소</dt><dd>{contract.property_address}</dd></div>
        </dl>
        <dl className="practice-drawer-amounts" aria-label="계약 금액">
          <div className="practice-drawer-amount--primary"><dt>보증금</dt><dd>{money.format(contract.deposit)}원</dd></div>
          <div><dt>계약금</dt><dd>{money.format(contract.contract_payment)}원</dd></div>
          <div><dt>잔금</dt><dd>{money.format(contract.balance_payment)}원</dd></div>
        </dl>
        {contract.special_clauses.length > 0 && (
          <div className="practice-drawer-clauses">
            <h3>특약</h3>
            <ol>{contract.special_clauses.map((clause) => <li key={clause}>{clause}</li>)}</ol>
          </div>
        )}
      </section>
  );
}

export function PracticeSessionPage() {
  const { sessionId = "" } = useParams();
  const navigate = useNavigate();
  const turnStartedAt = useRef(Date.now());
  const [session, setSession] = useState<PracticeSessionDto | null>(null);
  const [scenario, setScenario] = useState<PracticeScenarioDetailDto | null>(null);
  const [lastResponse, setLastResponse] = useState<PracticeTurnResponseDto | null>(null);
  const [latestConversationTurn, setLatestConversationTurn] = useState<PracticeConversationTurnDto | null>(null);
  const [conversationRefreshToken, setConversationRefreshToken] = useState(0);
  const [answer, setAnswer] = useState("");
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [submitting, setSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [drawerTab, setDrawerTab] = useState<"contract" | "conversation">("conversation");
  const [conversationOpen, setConversationOpen] = useState(isWideViewport);
  const [avatarMedia, setAvatarMedia] = useState<PracticeMediaJobDto | null>(null);
  const [avatarVideoUrl, setAvatarVideoUrl] = useState<string | null>(null);
  const [avatarSpeechText, setAvatarSpeechText] = useState<string | null>(null);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const speechBaseAnswerRef = useRef("");
  const [isListening, setIsListening] = useState(false);
  const [speechMessage, setSpeechMessage] = useState("");

  async function loadSession() {
    setStatus("loading");
    setDrawerTab("conversation");
    setConversationOpen(isWideViewport());
    try {
      const loaded = await practiceService.getSession(sessionId);
      if (loaded.status === "completed") {
        navigate(`/practice/sessions/${sessionId}/result`, { replace: true });
        return;
      }
      setSession(loaded);
      try {
        const latestMedia = await practiceService.getLatestMedia(sessionId);
        setAvatarMedia(latestMedia);
        setAvatarSpeechText(latestMedia?.speech_text ?? null);
      } catch {
        setAvatarMedia(null);
        setAvatarSpeechText(null);
      }
      try {
        setScenario(await practiceService.getScenario(loaded.scenario_id));
      } catch {
        setScenario(null);
      }
      turnStartedAt.current = Date.now();
      setStatus("success");
    } catch {
      setErrorMessage("연습을 불러오지 못했습니다. 이전에 저장된 연습 내용은 그대로 있습니다. 다시 시도해 주세요.");
      setStatus("error");
    }
  }

  useEffect(() => { void loadSession(); }, [sessionId]);

  useEffect(() => () => {
    recognitionRef.current?.abort();
    recognitionRef.current = null;
  }, []);

  useEffect(() => {
    if (!avatarMedia || avatarMedia.status === "completed" || avatarMedia.status === "failed") return;
    let cancelled = false;
    let timer: number | undefined;

    async function poll() {
      try {
        const latest = await practiceService.getMediaJob(avatarMedia!.media_job_id);
        if (cancelled) return;
        setAvatarMedia(latest);
        if (latest.status !== "failed") {
          timer = window.setTimeout(() => void poll(), 1500);
        }
      } catch {
        if (!cancelled) {
          setAvatarMedia((current) => current ? { ...current, status: "failed", error_code: "media_poll_failed" } : null);
        }
      }
    }

    timer = window.setTimeout(() => void poll(), 500);
    return () => {
      cancelled = true;
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, [avatarMedia?.media_job_id, avatarMedia?.status]);

  useEffect(() => {
    if (
      avatarMedia?.status !== "completed"
      || !avatarMedia.video_url
      || avatarVideoUrl
    ) return;
    let cancelled = false;

    void practiceService.getMediaVideo(avatarMedia.video_url)
      .then((video) => {
        if (cancelled) return;
        setAvatarVideoUrl(URL.createObjectURL(video));
      })
      .catch(() => {
        if (!cancelled) {
          setAvatarMedia((current) => current ? {
            ...current,
            status: "failed",
            error_code: "media_download_failed",
          } : null);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [avatarMedia?.status, avatarMedia?.video_url, avatarVideoUrl]);

  useEffect(() => () => {
    if (avatarVideoUrl) URL.revokeObjectURL(avatarVideoUrl);
  }, [avatarVideoUrl]);

  async function sendTurn(timedOut: boolean) {
    if (!session?.current_turn || (!timedOut && !answer.trim())) return;
    recognitionRef.current?.stop();
    const answeredTurn = session.current_turn;
    const submittedAnswer = timedOut ? null : answer.trim();
    setSubmitting(true);
    setErrorMessage("");
    try {
      const response = await practiceService.submitTurn(sessionId, {
        request_id: createPracticeRequestId("turn"),
        turn_id: session.current_turn.turn_id,
        user_answer: timedOut ? null : answer.trim(),
        timed_out: timedOut,
        response_time_seconds: elapsedSeconds(turnStartedAt.current),
      });
      setLastResponse(response);
      setAvatarMedia(response.media ?? null);
      // 아바타는 방금 answer에 대한 상대방 반응을 말한다. 반응이 없으면 현재 장면 대사.
      setAvatarSpeechText(response.dialogue_response ?? response.session.current_turn?.prompt ?? null);
      setAvatarVideoUrl((current) => {
        if (current) URL.revokeObjectURL(current);
        return null;
      });
      setSession(response.session);
      setLatestConversationTurn({
        practice_turn_id: response.practice_turn_id,
        turn_id: answeredTurn.turn_id,
        prompt: answeredTurn.prompt,
        user_answer: submittedAnswer,
        timed_out: timedOut,
        dialogue_response: response.dialogue_response,
        created_at: new Date().toISOString(),
      });
      setConversationRefreshToken((current) => current + 1);
      setAnswer("");
      turnStartedAt.current = Date.now();
    } catch {
      setErrorMessage("답변을 보내지 못했습니다. 입력한 답변은 그대로 남아 있습니다. 다시 시도해 주세요.");
    } finally {
      setSubmitting(false);
    }
  }

  async function advanceDialogue() {
    if (!session?.current_turn) return;
    setSubmitting(true);
    setErrorMessage("");
    try {
      const response = await practiceService.advanceDialogue(sessionId, {
        request_id: createPracticeRequestId("advance"),
        turn_id: session.current_turn.turn_id,
        destination: "next_turn",
      });
      setSession(response.session);
      setLastResponse(null);
      setAvatarMedia(null);
      setAvatarVideoUrl((current) => {
        if (current) URL.revokeObjectURL(current);
        return null;
      });
      // provider 오류 복구로 대화를 계속할 때 직전 오류 응답과 미디어를 초기화한다.
      setAvatarSpeechText(null);
      turnStartedAt.current = Date.now();
    } catch {
      setErrorMessage("대화를 이어가지 못했습니다. 현재 연습 내용은 그대로입니다. 다시 시도해 주세요.");
    } finally {
      setSubmitting(false);
    }
  }

  function submitAnswer(event: FormEvent) {
    event.preventDefault();
    void sendTurn(false);
  }

  function toggleSpeechInput() {
    if (isListening) {
      recognitionRef.current?.stop();
      return;
    }

    const SpeechRecognition = getSpeechRecognitionConstructor();
    if (!SpeechRecognition) {
      setSpeechMessage("이 브라우저에서는 음성 입력을 지원하지 않습니다. 텍스트로 입력해 주세요.");
      return;
    }

    const recognition = new SpeechRecognition();
    let endedWithError = false;
    speechBaseAnswerRef.current = answer.trim();
    recognition.lang = "ko-KR";
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.onresult = (event) => {
      const transcript = Array.from(event.results)
        .map((result) => result[0]?.transcript ?? "")
        .join(" ")
        .trim();
      const nextAnswer = [speechBaseAnswerRef.current, transcript].filter(Boolean).join(" ");
      setAnswer(nextAnswer.slice(0, 2000));
    };
    recognition.onerror = (event) => {
      endedWithError = true;
      setSpeechMessage(speechRecognitionErrorMessage(event.error));
      setIsListening(false);
    };
    recognition.onend = () => {
      recognitionRef.current = null;
      setIsListening(false);
      if (!endedWithError) setSpeechMessage("음성 입력이 완료되었습니다.");
    };

    recognitionRef.current = recognition;
    setSpeechMessage("듣고 있습니다. 말씀해 주세요.");
    setIsListening(true);
    try {
      recognition.start();
    } catch {
      recognitionRef.current = null;
      setIsListening(false);
      setSpeechMessage("음성 입력을 시작하지 못했습니다. 다시 시도하거나 텍스트로 입력해 주세요.");
    }
  }

  function handleAnswerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    const isDesktopKeyboard = window.matchMedia?.("(hover: hover) and (pointer: fine)")?.matches ?? false;
    if (event.key !== "Enter" || event.shiftKey || event.nativeEvent.isComposing || !isDesktopKeyboard || submitting || !answer.trim()) return;
    event.preventDefault();
    void sendTurn(false);
  }

  async function decideContract(selectedAction: PracticeSelectedAction) {
    setSubmitting(true);
    setErrorMessage("");
    try {
      await practiceService.submitFinalAction(sessionId, {
        request_id: createPracticeRequestId("final"),
        selected_action: selectedAction,
        response_time_seconds: elapsedSeconds(turnStartedAt.current),
      });
      navigate(`/practice/sessions/${sessionId}/result`);
    } catch {
      setErrorMessage("선택을 저장하지 못했습니다. 다시 시도해 주세요.");
      setSubmitting(false);
    }
  }

  // 재도전은 진행한 세션을 되감지 않고 같은 시나리오로 새 세션을 연다.
  async function retryScenario() {
    if (!session) return;
    setSubmitting(true);
    setErrorMessage("");
    try {
      const created = await practiceService.createSession(session.scenario_id);
      navigate(`/practice/sessions/${created.practice_session_id}`);
    } catch {
      setErrorMessage("다시 시작하지 못했습니다. 다시 시도해 주세요.");
      setSubmitting(false);
    }
  }

  const isActionSelection = session?.current_state === "ACTION-SELECTION";
  const evaluationNotice = practiceEvaluationNotice(lastResponse);
  // 상대방 반응은 대화 기록에 쌓이고, 큰 화면에는 지금 답할 대사만 표시한다.
  const brokerSpeech = avatarSpeechText ?? session?.current_turn?.prompt ?? "";

  return (
    <PageShell layout="workspace" step="계약 연습" title="상대방에게 직접 말해 보세요" description="상대방의 말을 듣고 자연스럽게 답해 보세요. 조심할 부분은 대화가 끝난 뒤 정리해 드립니다." showJourney={false}>
      <div className="stack">
        {status === "loading" && <LoadingState title="대화 상태를 불러오는 중" description="마지막으로 저장된 턴부터 이어서 준비합니다." />}
        {status === "error" && <ErrorState title="대화를 불러오지 못했습니다" description={errorMessage} onRetry={() => void loadSession()} />}
        {status === "success" && session && (
          <>
            {!isActionSelection && session.current_turn && (
              <>
                <div className={`practice-session-stage${conversationOpen ? " practice-session-stage--open" : ""}`}>
                  <aside className="practice-conversation-drawer" aria-label="계약서와 대화 내용">
                    <div className="practice-drawer-tabs" role="tablist" aria-label="계약서와 대화 내용">
                      <button type="button" role="tab" id="drawer-tab-contract" aria-selected={drawerTab === "contract"} className={drawerTab === "contract" ? "is-active" : ""} onClick={() => setDrawerTab("contract")}>계약서</button>
                      <button type="button" role="tab" id="drawer-tab-conversation" aria-selected={drawerTab === "conversation"} className={drawerTab === "conversation" ? "is-active" : ""} onClick={() => setDrawerTab("conversation")}>대화 내용</button>
                      <button type="button" className="secondary practice-drawer-close" onClick={() => setConversationOpen(false)} aria-label="이전 대화 닫기">닫기</button>
                    </div>
                    <div className="practice-drawer-panel">
                      {drawerTab === "contract"
                        ? (scenario
                            ? <ContractReference scenario={scenario} />
                            : <p className="practice-chat__empty" role="tabpanel" aria-labelledby="drawer-tab-contract">계약 내용을 불러오지 못했습니다.</p>)
                        : <PracticeChatPanel
                            sessionId={session.practice_session_id}
                            currentTurn={session.current_turn}
                            latestTurn={latestConversationTurn}
                            refreshToken={conversationRefreshToken}
                          />}
                    </div>
                  </aside>
                  <div className="practice-session-stage__main">
                    <PracticeAvatarStage
                      scenarioId={scenario?.scenario_id ?? session.scenario_id}
                      prompt={brokerSpeech}
                      pressureDelaySeconds={session.current_turn.wait_sequence.find((step) => step.state === "WAIT_PRESSURE")?.from_second ?? null}
                      hasUserInput={Boolean(answer.trim())}
                      submitting={submitting}
                      generatedVideoUrl={avatarVideoUrl}
                      mediaStatus={avatarMedia?.status ?? null}
                      onToggleConversation={() => setConversationOpen((open) => !open)}
                      conversationOpen={conversationOpen}
                    />
                    <section className="practice-dialogue practice-dialogue--composer" aria-label="현재 답변">
                      <form className="practice-answer-composer" onSubmit={submitAnswer}>
                        <div className="practice-answer-composer__row">
                          <button
                            type="button"
                            className="secondary practice-answer-composer__speech"
                            aria-controls="practice-answer"
                            aria-pressed={isListening}
                            disabled={submitting}
                            onClick={toggleSpeechInput}
                          >
                            {isListening ? "듣는 중…" : "말하기"}
                          </button>
                          <textarea id="practice-answer" aria-label="내 답변" value={answer} maxLength={2000} onChange={(event) => setAnswer(event.target.value)} onKeyDown={handleAnswerKeyDown} placeholder="하고 싶은 말을 입력하세요…" disabled={submitting} />
                          <button type="submit" className="primary" disabled={submitting || !answer.trim()}>{submitting ? "전송 중…" : "전송"}</button>
                        </div>
                        {speechMessage && <p className="practice-answer-speech-status" role="status" aria-live="polite">{speechMessage}</p>}
                        <p className="practice-answer-shortcut">Enter로 보내기 · Shift+Enter로 줄바꿈</p>
                        <button type="button" className="secondary practice-answer-composer__skip" disabled={submitting} onClick={() => void sendTurn(true)}>답변하지 못했어요</button>
                      </form>
                      {evaluationNotice && (
                        <>
                          <p className="notice" role="alert">{evaluationNotice}</p>
                          <div className="practice-dialogue-actions" aria-label="연습 계속하기">
                            <button type="button" className="secondary" disabled={submitting} onClick={() => setLastResponse(null)}>다시 확인하기</button>
                            <button type="button" className="secondary" disabled={submitting} onClick={() => void advanceDialogue()}>대화를 계속하기</button>
                          </div>
                        </>
                      )}
                    </section>
                  </div>
                </div>
              </>
            )}
            {isActionSelection && (
              <section className="practice-final-actions" aria-labelledby="practice-final-title">
                <h2 id="practice-final-title">계약하시겠습니까?</h2>
                <p>지금까지 확인한 내용을 기준으로 오늘 계약을 진행할지 정해 주세요. 선택에 따라 결과가 달라집니다.</p>
                <div className="practice-dialogue-actions">
                  <button type="button" className="primary" disabled={submitting} onClick={() => void decideContract("진행")}>
                    {submitting ? "정리 중…" : "네, 계약하겠습니다"}
                  </button>
                  <button type="button" className="secondary" disabled={submitting} onClick={() => void decideContract("중단")}>
                    아니요, 오늘은 진행하지 않겠습니다
                  </button>
                </div>
                <button type="button" className="text-link" disabled={submitting} onClick={() => void retryScenario()}>
                  처음부터 다시 연습하기
                </button>
              </section>
            )}
            {errorMessage && <p className="notice" role="alert">{errorMessage}</p>}
            <Link className="text-link" to="/practice">연습 목록으로 나가기</Link>
          </>
        )}
      </div>
    </PageShell>
  );
}
