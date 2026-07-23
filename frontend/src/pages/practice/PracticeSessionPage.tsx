import { FormEvent, KeyboardEvent, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ErrorState, LoadingState } from "../../components/feedback/AsyncState";
import { PageShell } from "../../components/layout/PageShell";
import { createPracticeRequestId, practiceService } from "../../services/practiceService";
import { PracticeAvatarStage } from "./PracticeAvatarStage";
import { PracticeHintPanel } from "./PracticeHintPanel";
import { PracticeChatPanel } from "./PracticeChatPanel";
import { PracticeMissionCard } from "./PracticeMissionCard";
import { practiceMissionForScenario } from "./practiceMissionCatalog";
import type {
  PracticeScenarioDetailDto,
  PracticeSelectedAction,
  PracticeSessionDto,
  PracticeConversationTurnDto,
  PracticeMediaJobDto,
  PracticeTurnResponseDto,
} from "../../types/api";

const money = new Intl.NumberFormat("ko-KR");

function elapsedSeconds(startedAt: number) {
  return Math.min(3600, Math.max(0, (Date.now() - startedAt) / 1000));
}

function practiceEvaluationNotice(response: PracticeTurnResponseDto | null) {
  const reason = response?.evaluation?.fallback_reason;
  return reason === "provider_error" || reason === "provider_timeout" || reason === "response_validation_failed"
    ? "답변을 확인하지 못했습니다. 입력한 내용은 잘못된 답변으로 처리하지 않았습니다. 연습은 계속할 수 있습니다."
    : null;
}

function ContractReference({ scenario, open, onToggle }: {
  scenario: PracticeScenarioDetailDto;
  open: boolean;
  onToggle: (open: boolean) => void;
}) {
  const contract = scenario.synthetic_contract;
  return (
    <details className="practice-contract-reference" onToggle={(event) => onToggle(event.currentTarget.open)}>
      <summary>계약 내용 참고하기</summary>
      <section className="practice-contract-card" aria-labelledby="practice-contract-reference-title" hidden={!open}>
        <h2 id="practice-contract-reference-title">계약 내용</h2>
        <dl className="practice-facts">
          <div><dt>계약 유형</dt><dd>{contract.contract_type}</dd></div>
          <div><dt>보증금</dt><dd>{money.format(contract.deposit)}원</dd></div>
          <div><dt>계약금</dt><dd>{money.format(contract.contract_payment)}원</dd></div>
          <div><dt>잔금</dt><dd>{money.format(contract.balance_payment)}원</dd></div>
          <div className="practice-facts__wide"><dt>주택 주소</dt><dd>{contract.property_address}</dd></div>
          <div className="practice-facts__wide"><dt>특약</dt><dd>{contract.special_clauses.join(" ")}</dd></div>
        </dl>
      </section>
    </details>
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
  const [hintOpen, setHintOpen] = useState(false);
  const [contractOpen, setContractOpen] = useState(false);
  const [selectedAction, setSelectedAction] = useState<PracticeSelectedAction | null>(null);
  const [conversationOpen, setConversationOpen] = useState(false);
  const [avatarMedia, setAvatarMedia] = useState<PracticeMediaJobDto | null>(null);
  const [avatarVideoUrl, setAvatarVideoUrl] = useState<string | null>(null);
  const [avatarSpeechText, setAvatarSpeechText] = useState<string | null>(null);

  async function loadSession() {
    setStatus("loading");
    setHintOpen(false);
    setContractOpen(false);
    setConversationOpen(false);
    setSelectedAction(null);
    try {
      const loaded = await practiceService.getSession(sessionId);
      if (loaded.status === "completed") {
        navigate(`/practice/sessions/${sessionId}/result`, { replace: true });
        return;
      }
      setSession(loaded);
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
      setAvatarSpeechText(response.dialogue_response);
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
      setHintOpen(false);
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
      setHintOpen(false);
      turnStartedAt.current = Date.now();
    } catch {
      setErrorMessage("다음 상황으로 이동하지 못했습니다. 현재 연습 내용은 그대로입니다. 다시 시도해 주세요.");
    } finally {
      setSubmitting(false);
    }
  }

  function submitAnswer(event: FormEvent) {
    event.preventDefault();
    void sendTurn(false);
  }

  function handleAnswerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    const isDesktopKeyboard = window.matchMedia?.("(hover: hover) and (pointer: fine)")?.matches ?? false;
    if (event.key !== "Enter" || event.shiftKey || event.nativeEvent.isComposing || !isDesktopKeyboard || submitting || !answer.trim()) return;
    event.preventDefault();
    void sendTurn(false);
  }

  async function chooseFinalAction() {
    if (!selectedAction) return;
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
      setErrorMessage("선택을 저장하지 못했습니다. 현재 선택은 그대로입니다. 다시 시도해 주세요.");
      setSubmitting(false);
    }
  }

  const isActionSelection = session?.current_state === "ACTION-SELECTION";
  const evaluationNotice = practiceEvaluationNotice(lastResponse);
  const confirmedCount = session?.confirmed_action_ids.length ?? 0;
  const mission = practiceMissionForScenario(session?.scenario_id ?? "");
  const progressText = mission.targetCount === null
    ? `확인 행동 ${confirmedCount}개`
    : `확인 행동 ${confirmedCount} / ${mission.targetCount}`;

  return (
    <PageShell layout="workspace" step="계약 연습" title="상대방에게 직접 말해 보세요" description="정답 문구를 외우기보다, 확인할 내용과 진행 보류 의사를 자신의 말로 표현하는 연습입니다." showJourney={false}>
      <div className="stack">
        {status === "loading" && <LoadingState title="대화 상태를 불러오는 중" description="마지막으로 저장된 턴부터 이어서 준비합니다." />}
        {status === "error" && <ErrorState title="대화를 불러오지 못했습니다" description={errorMessage} onRetry={() => void loadSession()} />}
        {status === "success" && session && (
          <>
            <div className="practice-progress" role="status" aria-live="polite">
              <span>미션 진행</span>
              <strong>{progressText}</strong>
            </div>
            <div className="practice-session-mission">
              <PracticeMissionCard scenarioId={session.scenario_id} confirmedCount={confirmedCount} showProgress={false} />
            </div>
            {!isActionSelection && session.current_turn && (
              <>
                {scenario && <ContractReference scenario={scenario} open={contractOpen} onToggle={setContractOpen} />}
                <PracticeAvatarStage
                  scenarioId={scenario?.scenario_id ?? session.scenario_id}
                  prompt={session.current_turn.prompt}
                  pressureDelaySeconds={session.current_turn.wait_sequence.find((step) => step.state === "WAIT_PRESSURE")?.from_second ?? null}
                  hasUserInput={Boolean(answer.trim())}
                  submitting={submitting}
                  generatedVideoUrl={avatarVideoUrl}
                  generatedSpeechText={avatarSpeechText}
                  mediaStatus={avatarMedia?.status ?? null}
                />
                <section className="practice-dialogue practice-dialogue--composer" aria-label="현재 답변">
                  <form className="practice-answer-composer" onSubmit={submitAnswer}>
                    <div className="practice-answer-composer__row">
                      <label htmlFor="practice-answer">말하기</label>
                      <textarea id="practice-answer" aria-label="내 답변" value={answer} maxLength={2000} onChange={(event) => setAnswer(event.target.value)} onKeyDown={handleAnswerKeyDown} placeholder="궁금한 내용이나 확인할 조건을 입력하세요…" disabled={submitting} />
                      <button type="submit" className="primary" disabled={submitting || !answer.trim()}>{submitting ? "확인 중…" : "이렇게 말할게요"}</button>
                    </div>
                    <p className="practice-answer-shortcut">Enter로 보내기 · Shift+Enter로 줄바꿈</p>
                    <button type="button" className="secondary practice-answer-composer__skip" disabled={submitting} onClick={() => void sendTurn(true)}>답변하지 못했어요</button>
                  </form>
                  {!hintOpen && <button type="button" className="secondary" disabled={submitting} onClick={() => setHintOpen(true)}>말할 내용 힌트 보기</button>}
                  {hintOpen && <PracticeHintPanel guide={mission.guide} prompt={session.current_turn.prompt} />}
                  {evaluationNotice && (
                    <>
                      <p className="notice" role="alert">{evaluationNotice}</p>
                      <div className="practice-dialogue-actions" aria-label="연습 계속하기">
                        <button type="button" className="secondary" disabled={submitting} onClick={() => setLastResponse(null)}>다시 확인하기</button>
                        <button type="button" className="secondary" disabled={submitting} onClick={() => void advanceDialogue()}>다음 상황으로</button>
                      </div>
                    </>
                  )}
                </section>
                <details className="practice-conversation-reference" onToggle={(event) => setConversationOpen(event.currentTarget.open)}>
                  <summary>이전 대화 보기</summary>
                  {conversationOpen && (
                    <PracticeChatPanel
                      sessionId={session.practice_session_id}
                      currentTurn={session.current_turn}
                      latestTurn={latestConversationTurn}
                      refreshToken={conversationRefreshToken}
                    />
                  )}
                </details>
              </>
            )}
            {isActionSelection && (
              <section className="practice-final-actions" aria-labelledby="practice-final-title">
                <h2 id="practice-final-title">연습 결과 확인하기</h2>
                <div className="practice-final-actions__grid">
                  {session.allowed_final_actions.map((action) => (
                    <button type="button" className="secondary" aria-pressed={selectedAction === action} disabled={submitting} onClick={() => setSelectedAction(action)} key={action}>{action}</button>
                  ))}
                </div>
                <button type="button" className="primary" disabled={submitting || !selectedAction} onClick={() => void chooseFinalAction()}>연습 결과 확인하기</button>
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
