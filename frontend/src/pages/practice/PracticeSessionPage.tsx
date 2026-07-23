import { FormEvent, KeyboardEvent, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ErrorState, LoadingState } from "../../components/feedback/AsyncState";
import { PageShell } from "../../components/layout/PageShell";
import { createPracticeRequestId, practiceService } from "../../services/practiceService";
import { PracticeAvatarStage } from "./PracticeAvatarStage";
import type {
  PracticeScenarioDetailDto,
  PracticeSelectedAction,
  PracticeSessionDto,
  PracticeTurnResponseDto,
} from "../../types/api";

interface DialogueHistoryItem {
  id: string;
  userAnswer: string;
  response: string | null;
}

const money = new Intl.NumberFormat("ko-KR");

function elapsedSeconds(startedAt: number) {
  return Math.min(3600, Math.max(0, (Date.now() - startedAt) / 1000));
}

function practiceEvaluationNotice(response: PracticeTurnResponseDto | null) {
  const reason = response?.evaluation?.fallback_reason;
  if (reason === "provider_error" || reason === "provider_timeout") {
    return "AI 연결이 원활하지 않아 답변을 판정하지 못했습니다. 잠시 후 다시 시도해 주세요.";
  }
  return null;
}

export function PracticeSessionPage() {
  const { sessionId = "" } = useParams();
  const navigate = useNavigate();
  const turnStartedAt = useRef(Date.now());
  const [session, setSession] = useState<PracticeSessionDto | null>(null);
  const [scenario, setScenario] = useState<PracticeScenarioDetailDto | null>(null);
  const [workspaceTab, setWorkspaceTab] = useState<"contract" | "conversation">("contract");
  const [contractPage, setContractPage] = useState(1);
  const [contractZoomed, setContractZoomed] = useState(false);
  const [lastResponse, setLastResponse] = useState<PracticeTurnResponseDto | null>(null);
  const [dialogueHistory, setDialogueHistory] = useState<DialogueHistoryItem[]>([]);
  const [answer, setAnswer] = useState("");
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [submitting, setSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  async function loadSession() {
    setStatus("loading");
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
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "연습 세션을 불러오지 못했습니다.");
      setStatus("error");
    }
  }

  useEffect(() => { void loadSession(); }, [sessionId]);

  async function sendTurn(timedOut: boolean) {
    if (!session?.current_turn || (!timedOut && !answer.trim())) return;
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
      setSession(response.session);
      setDialogueHistory((current) => [
        ...current,
        {
          id: response.practice_turn_id,
          userAnswer: timedOut ? "답변하지 못했어요." : answer.trim(),
          response: timedOut
            ? response.dialogue_response
            : response.session.current_turn?.prompt ?? response.dialogue_response,
        },
      ]);
      setAnswer("");
      turnStartedAt.current = Date.now();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "답변을 보내지 못했습니다.");
    } finally {
      setSubmitting(false);
    }
  }

  async function advanceDialogue(destination: "next_turn" | "action_selection") {
    if (!session?.current_turn) return;
    setSubmitting(true);
    setErrorMessage("");
    try {
      const response = await practiceService.advanceDialogue(sessionId, {
        request_id: createPracticeRequestId("advance"),
        turn_id: session.current_turn.turn_id,
        destination,
      });
      setSession(response.session);
      setLastResponse(null);
      turnStartedAt.current = Date.now();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "다음 상황으로 이동하지 못했습니다.");
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
    if (
      event.key !== "Enter"
      || event.shiftKey
      || event.nativeEvent.isComposing
      || !isDesktopKeyboard
      || submitting
      || !answer.trim()
    ) return;
    event.preventDefault();
    void sendTurn(false);
  }

  async function chooseFinalAction(selectedAction: PracticeSelectedAction) {
    setSubmitting(true);
    setErrorMessage("");
    try {
      await practiceService.submitFinalAction(sessionId, {
        request_id: createPracticeRequestId("final"),
        selected_action: selectedAction,
        response_time_seconds: elapsedSeconds(turnStartedAt.current),
      });
      navigate(`/practice/sessions/${sessionId}/result`);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "최종 행동을 저장하지 못했습니다.");
      setSubmitting(false);
    }
  }

  const isActionSelection = session?.current_state === "ACTION-SELECTION";
  const evaluationNotice = practiceEvaluationNotice(lastResponse);

  return (
    <PageShell layout="workspace" step="계약 연습" title="상대방에게 직접 말해 보세요" description="정답 문구를 외우기보다, 확인할 내용과 진행 보류 의사를 자신의 말로 표현하는 연습입니다." showJourney={false}>
      <div className="stack">
        {status === "loading" && <LoadingState title="대화 상태를 불러오는 중" description="마지막으로 저장된 턴부터 이어서 준비합니다." />}
        {status === "error" && <ErrorState title="대화를 불러오지 못했습니다" description={errorMessage} onRetry={() => void loadSession()} />}
        {status === "success" && session && (
          <>
            <div className="practice-progress" role="status" aria-label="연습 진행 상태" aria-live="polite">
              <span>현재 단계 <strong>{isActionSelection ? "최종 행동 선택" : session.current_turn?.turn_id}</strong></span>
              <span>확인한 행동 <strong>{session.confirmed_action_ids.length}개</strong></span>
            </div>
            {!isActionSelection && session.current_turn && scenario && (
              <section className="practice-simulation-workspace" aria-label="계약서와 공인중개사 대화 화면">
                <div className="practice-document-viewer">
                  <div className="practice-workspace-tabs" role="tablist" aria-label="연습 자료 보기">
                    <button type="button" role="tab" aria-selected={workspaceTab === "contract"} onClick={() => setWorkspaceTab("contract")}>계약서</button>
                    <button type="button" role="tab" aria-selected={workspaceTab === "conversation"} onClick={() => setWorkspaceTab("conversation")}>
                      대화 내용 {dialogueHistory.length > 0 && <span className="practice-tab-dot" aria-label="새 대화 있음">●</span>}
                    </button>
                  </div>
                  {workspaceTab === "contract" ? (
                    <article className={`practice-contract-document${contractZoomed ? " practice-contract-document--zoomed" : ""}`} aria-labelledby="practice-contract-reference-title">
                      <header>
                        <h2 id="practice-contract-reference-title">주택임대차계약서</h2>
                        <h3>
                          {contractPage === 1 ? "1. 기본 계약 내용" : contractPage === 2 ? "2. 일반 계약 조항" : "3. 특약사항"}
                        </h3>
                      </header>
                      <div className="practice-contract-document__page">
                        {contractPage === 1 && (
                          <dl className="practice-contract-document__facts">
                            <div><dt>계약 유형</dt><dd>{scenario.synthetic_contract.contract_type}</dd></div>
                            <div><dt>보증금</dt><dd>{money.format(scenario.synthetic_contract.deposit)}원</dd></div>
                            <div><dt>계약금</dt><dd>{money.format(scenario.synthetic_contract.contract_payment)}원</dd></div>
                            <div><dt>잔금</dt><dd>{money.format(scenario.synthetic_contract.balance_payment)}원</dd></div>
                            <div><dt>임대인</dt><dd>{scenario.synthetic_contract.landlord_name}</dd></div>
                            <div><dt>공인중개사</dt><dd>{scenario.synthetic_contract.broker_name}</dd></div>
                            <div><dt>계약 기간</dt><dd>{scenario.synthetic_contract.start_date} ~ {scenario.synthetic_contract.end_date}</dd></div>
                            <div><dt>주택 주소</dt><dd>{scenario.synthetic_contract.property_address}</dd></div>
                          </dl>
                        )}
                        {contractPage === 2 && (
                          <ol className="practice-contract-document__clauses">
                            <li>임대차 기간은 {scenario.synthetic_contract.start_date}부터 {scenario.synthetic_contract.end_date}까지로 한다.</li>
                            <li>계약금 {money.format(scenario.synthetic_contract.contract_payment)}원은 {scenario.synthetic_contract.contract_payment_date}에, 잔금 {money.format(scenario.synthetic_contract.balance_payment)}원은 {scenario.synthetic_contract.balance_payment_date}에 지급한다.</li>
                            <li>{scenario.synthetic_contract.deposit_return_clause}</li>
                          </ol>
                        )}
                        {contractPage === 3 && (
                          <ol className="practice-contract-document__clauses">
                            {scenario.synthetic_contract.special_clauses.map((clause) => <li key={clause}>{clause}</li>)}
                          </ol>
                        )}
                      </div>
                      <footer className="practice-contract-document__footer">
                        <span>{contractPage} / 3 페이지</span>
                        <div>
                          <button type="button" className="secondary" disabled={contractPage === 1} onClick={() => setContractPage((page) => Math.max(1, page - 1))}>이전</button>
                          <button type="button" className="secondary" disabled={contractPage === 3} onClick={() => setContractPage((page) => Math.min(3, page + 1))}>다음</button>
                          <button type="button" className="secondary" aria-pressed={contractZoomed} onClick={() => setContractZoomed((zoomed) => !zoomed)}>{contractZoomed ? "축소" : "확대"}</button>
                        </div>
                      </footer>
                    </article>
                  ) : (
                    <section className="practice-conversation-history practice-conversation-history--panel" role="tabpanel" aria-label="지금까지의 대화" aria-live="polite">
                      <h2>지금까지의 대화</h2>
                      {dialogueHistory.length === 0 ? <p className="practice-conversation-history__empty">아직 주고받은 대화가 없습니다.</p> : (
                        <ol>
                          {dialogueHistory.map((item) => (
                            <li key={item.id}>
                              <div className="practice-conversation-history__user"><strong>나</strong><p>{item.userAnswer}</p></div>
                              {item.response && <div className="practice-conversation-history__counterparty"><strong>상대방</strong><p>{item.response}</p></div>}
                            </li>
                          ))}
                        </ol>
                      )}
                    </section>
                  )}
                </div>
                <PracticeAvatarStage
                  prompt={session.current_turn.prompt}
                  pressureDelaySeconds={session.current_turn.wait_sequence.find((step) => step.state === "WAIT_PRESSURE")?.from_second ?? null}
                  hasUserInput={Boolean(answer.trim())}
                  submitting={submitting}
                />
              </section>
            )}
            {!isActionSelection && session.current_turn && !scenario && (
              <PracticeAvatarStage
                prompt={session.current_turn.prompt}
                pressureDelaySeconds={session.current_turn.wait_sequence.find((step) => step.state === "WAIT_PRESSURE")?.from_second ?? null}
                hasUserInput={Boolean(answer.trim())}
                submitting={submitting}
              />
            )}
            {!isActionSelection && session.current_turn && (
              <section className="practice-dialogue practice-dialogue--composer" aria-labelledby="practice-prompt-title">
                <p className="sr-only">공인중개사의 말</p>
                <span className="sr-only" id="practice-prompt-title">현재 대사에 대한 답변 입력</span>
                {session.current_turn.wait_sequence.some((step) => step.line) && (
                  <p className="practice-pressure-hint">잠시 뒤 상대방이 재촉할 수 있습니다. 서두르지 말고 확인할 내용을 말해 보세요.</p>
                )}
                <form className="practice-answer-composer" onSubmit={submitAnswer}>
                  <div className="practice-answer-composer__row">
                    <label htmlFor="practice-answer">말하기</label>
                    <textarea id="practice-answer" aria-label="내 답변" value={answer} maxLength={2000} onChange={(event) => setAnswer(event.target.value)} onKeyDown={handleAnswerKeyDown} placeholder="궁금한 내용이나 확인할 조건을 입력하세요…" disabled={submitting} />
                    <button type="submit" aria-label="답변 보내기" disabled={submitting || !answer.trim()}>{submitting ? "확인 중…" : "전송"}</button>
                  </div>
                  <p className="practice-answer-shortcut">Enter로 보내기 · Shift+Enter로 줄바꿈</p>
                  <button type="button" className="secondary practice-answer-composer__skip" disabled={submitting} onClick={() => void sendTurn(true)}>답변하지 못했어요</button>
                </form>
                <div className="practice-dialogue-actions" aria-label="대화 진행 선택">
                  <button type="button" className="secondary" disabled={submitting} onClick={() => void advanceDialogue("next_turn")}>이 확인은 남기고 다음 상황</button>
                  <button type="button" className="secondary" disabled={submitting} onClick={() => void advanceDialogue("action_selection")}>대화를 마치고 최종 행동 선택</button>
                </div>
                {lastResponse?.attempt_no && lastResponse.attempt_no >= 2 && (
                  <p className="practice-loop-help">같은 확인이 반복되고 있습니다. 더 질문하거나, 미확인으로 남기고 다음 상황으로 넘어갈 수 있습니다.</p>
                )}
                {evaluationNotice && <p className="notice" role="alert">{evaluationNotice}</p>}
              </section>
            )}
            {isActionSelection && (
              <section className="practice-final-actions" aria-labelledby="practice-final-title">
                <p>대화를 마친 뒤</p>
                <h2 id="practice-final-title">이 계약 상황에서 어떻게 행동하시겠습니까?</h2>
                <div className="practice-final-actions__grid">
                  {session.allowed_final_actions.map((action) => (
                    <button type="button" disabled={submitting} onClick={() => void chooseFinalAction(action)} key={action}>{action}</button>
                  ))}
                </div>
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
