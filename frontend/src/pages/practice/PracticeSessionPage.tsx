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

// 연습을 끝낼지 되물어야 하는 행동 의도. `추가 확인`·`특약 수정 요구`는 대화를 이어 가는
// 의도이므로 기록만 하고 확인 화면을 띄우지 않는다. 시나리오가 허용하는 최종 선택지
// (allowed_final_actions)에 없는 `특약 수정 요구`를 제출하지 않기 위한 구분이기도 하다.
const terminalIntents: PracticeSelectedAction[] = ["진행", "보류", "중단"];

// 반응 영상이 끝났다는 신호가 오지 않아도 대화가 멈추지 않도록 두는 상한.
const reactionMaxSeconds = 15;

const intentQuestions: Record<string, string> = {
  진행: "이대로 계약을 진행하시겠습니까?",
  보류: "오늘은 계약을 보류하시겠습니까?",
  중단: "계약을 중단하시겠습니까?",
};

// 데스크탑(2단)에서는 이전 대화를 기본으로 펼쳐 두고, 모바일(오버레이)에서는 접어 둔다.
function isWideViewport() {
  return typeof window !== "undefined" && Boolean(window.matchMedia?.("(min-width: 900px)").matches);
}

function elapsedSeconds(startedAt: number) {
  return Math.min(3600, Math.max(0, (Date.now() - startedAt) / 1000));
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
  // 상대방 반응을 재생하는 동안에는 다음 질문을 보여 주지 않고 입력도 받지 않는다.
  const [reactionPlaying, setReactionPlaying] = useState(false);
  // 답변에서 읽은 계약 행동 의도. 바로 끝내지 않고 사용자에게 한 번 되묻는다.
  const [pendingIntent, setPendingIntent] = useState<PracticeSelectedAction | null>(null);
  const [dismissedIntents, setDismissedIntents] = useState<PracticeSelectedAction[]>([]);

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
      // 다음 장면으로 넘어갈 때만 반응을 먼저 재생하고 질문을 미룬다. 같은 장면에 머무는
      // 재질문·provider 복구는 반응 자체가 그 장면의 대사이므로 미룰 것이 없고, 대화가
      // 끝났으면 곧바로 최종 선택 화면으로 넘어가던 기존 흐름을 유지한다.
      const nextTurnId = response.session.current_turn?.turn_id;
      setReactionPlaying(
        Boolean(response.dialogue_response) && Boolean(nextTurnId) && nextTurnId !== answeredTurn.turn_id,
      );
      const intent = response.evaluation?.action_intent ?? null;
      setPendingIntent(
        intent && terminalIntents.includes(intent) && !dismissedIntents.includes(intent)
          ? intent
          : null,
      );
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

  // 반응 재생이 끝나면 미뤄 둔 다음 질문을 보여 준다. 대사를 비우면 아바타가 현재
  // TURN 질문을 다시 말한다.
  function finishReaction() {
    if (!reactionPlaying) return;
    setReactionPlaying(false);
    setAvatarSpeechText(null);
  }

  useEffect(() => {
    if (!reactionPlaying) return;
    const timer = window.setTimeout(finishReaction, reactionMaxSeconds * 1000);
    return () => window.clearTimeout(timer);
  }, [reactionPlaying]);

  // 대화 도중 읽은 행동 의도는 사용자가 확인해야 최종 선택으로 확정된다.
  async function confirmIntent(intent: PracticeSelectedAction) {
    if (!session) return;
    setSubmitting(true);
    setErrorMessage("");
    try {
      if (session.current_state !== "ACTION-SELECTION" && session.current_turn) {
        await practiceService.advanceDialogue(sessionId, {
          request_id: createPracticeRequestId("advance"),
          turn_id: session.current_turn.turn_id,
          destination: "action_selection",
        });
      }
      await practiceService.submitFinalAction(sessionId, {
        request_id: createPracticeRequestId("final"),
        selected_action: intent,
        response_time_seconds: elapsedSeconds(turnStartedAt.current),
      });
      navigate(`/practice/sessions/${sessionId}/result`);
    } catch {
      setErrorMessage("선택을 저장하지 못했습니다. 연습 내용은 그대로입니다. 다시 시도해 주세요.");
      setSubmitting(false);
    }
  }

  function dismissIntent(intent: PracticeSelectedAction) {
    // 같은 의도로 확인 화면을 반복해서 띄우지 않는다.
    setDismissedIntents((current) => current.includes(intent) ? current : [...current, intent]);
    setPendingIntent(null);
  }

  function submitAnswer(event: FormEvent) {
    event.preventDefault();
    void sendTurn(false);
  }

  function handleAnswerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    const isDesktopKeyboard = window.matchMedia?.("(hover: hover) and (pointer: fine)")?.matches ?? false;
    if (event.key !== "Enter" || event.shiftKey || event.nativeEvent.isComposing || !isDesktopKeyboard || inputLocked || !answer.trim()) return;
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
  // 반응 재생 중과 종료 확인 중에는 새 답변을 받지 않는다.
  const inputLocked = submitting || reactionPlaying || pendingIntent !== null;
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
                            // 반응이 끝나기 전에는 다음 질문을 대화 기록에도 미리 띄우지 않는다.
                            currentTurn={reactionPlaying ? null : session.current_turn}
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
                      onSpeechEnd={finishReaction}
                    />
                    <section className="practice-dialogue practice-dialogue--composer" aria-label="현재 답변">
                      {pendingIntent && !reactionPlaying && (
                        <div className="practice-intent-confirm" role="group" aria-labelledby="practice-intent-title">
                          <h3 id="practice-intent-title">{intentQuestions[pendingIntent]}</h3>
                          <p>지금 끝내면 지금까지 확인한 내용으로 결과를 정리해 드립니다.</p>
                          <div className="practice-dialogue-actions">
                            <button type="button" className="primary" disabled={submitting} onClick={() => void confirmIntent(pendingIntent)}>
                              {submitting ? "정리 중…" : "네, 이렇게 하겠습니다"}
                            </button>
                            <button type="button" className="secondary" disabled={submitting} onClick={() => dismissIntent(pendingIntent)}>
                              아니요, 대화를 더 하겠습니다
                            </button>
                          </div>
                        </div>
                      )}
                      <form className="practice-answer-composer" onSubmit={submitAnswer}>
                        <div className="practice-answer-composer__row">
                          <label htmlFor="practice-answer">말하기</label>
                          <textarea id="practice-answer" aria-label="내 답변" value={answer} maxLength={2000} onChange={(event) => setAnswer(event.target.value)} onKeyDown={handleAnswerKeyDown} placeholder={reactionPlaying ? "공인중개사의 말이 끝나면 답할 수 있습니다…" : "하고 싶은 말을 입력하세요…"} disabled={inputLocked} />
                          <button type="submit" className="primary" disabled={inputLocked || !answer.trim()}>{submitting ? "확인 중…" : "이렇게 말할게요"}</button>
                        </div>
                        <p className="practice-answer-shortcut">Enter로 보내기 · Shift+Enter로 줄바꿈</p>
                        <button type="button" className="secondary practice-answer-composer__skip" disabled={inputLocked} onClick={() => void sendTurn(true)}>답변하지 못했어요</button>
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
