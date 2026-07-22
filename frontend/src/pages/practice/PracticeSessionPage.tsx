import { FormEvent, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ErrorState, LoadingState } from "../../components/feedback/AsyncState";
import { PageShell } from "../../components/layout/PageShell";
import { createPracticeRequestId, practiceService } from "../../services/practiceService";
import type {
  PracticeAnswerCategory,
  PracticeSelectedAction,
  PracticeSessionDto,
  PracticeTurnResponseDto,
} from "../../types/api";

const categoryLabels: Record<PracticeAnswerCategory, string> = {
  appropriate_check: "필요한 확인 행동이 전달되었습니다.",
  partial_check: "확인 대상을 조금 더 구체적으로 말해 보세요.",
  ambiguous_answer: "진행 여부와 확인 요청을 더 분명히 말해 보세요.",
  avoidance: "질문을 피하지 말고 확인할 내용을 직접 말해 보세요.",
  no_response: "답변하지 못한 턴입니다. 같은 상황에서 다시 답할 수 있습니다.",
  needs_review: "답변을 자동으로 평가하지 못했습니다. 같은 턴에서 다시 답해 주세요.",
};

function elapsedSeconds(startedAt: number) {
  return Math.min(3600, Math.max(0, (Date.now() - startedAt) / 1000));
}

export function PracticeSessionPage() {
  const { sessionId = "" } = useParams();
  const navigate = useNavigate();
  const turnStartedAt = useRef(Date.now());
  const [session, setSession] = useState<PracticeSessionDto | null>(null);
  const [lastResponse, setLastResponse] = useState<PracticeTurnResponseDto | null>(null);
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
      setAnswer("");
      turnStartedAt.current = Date.now();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "답변을 보내지 못했습니다.");
    } finally {
      setSubmitting(false);
    }
  }

  function submitAnswer(event: FormEvent) {
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

  return (
    <PageShell layout="workspace" step="계약 연습" title="상대방에게 직접 말해 보세요" description="정답 문구를 외우기보다, 확인할 내용과 진행 보류 의사를 자신의 말로 표현하는 연습입니다." showJourney={false}>
      <div className="stack">
        {status === "loading" && <LoadingState title="대화 상태를 불러오는 중" description="마지막으로 저장된 턴부터 이어서 준비합니다." />}
        {status === "error" && <ErrorState title="대화를 불러오지 못했습니다" description={errorMessage} onRetry={() => void loadSession()} />}
        {status === "success" && session && (
          <>
            <div className="practice-progress" aria-label="연습 진행 상태">
              <span>현재 단계 <strong>{isActionSelection ? "최종 행동 선택" : session.current_turn?.turn_id}</strong></span>
              <span>확인한 행동 <strong>{session.confirmed_action_ids.length}개</strong></span>
            </div>
            {lastResponse?.dialogue_response && (
              <section className="practice-feedback" aria-live="polite">
                <p>상대방의 반응</p>
                <blockquote>{lastResponse.dialogue_response}</blockquote>
                {lastResponse.evaluation && <strong>{categoryLabels[lastResponse.evaluation.answer_category]}</strong>}
              </section>
            )}
            {!isActionSelection && session.current_turn && (
              <section className="practice-dialogue" aria-labelledby="practice-prompt-title">
                <p>임대인 또는 공인중개사의 말</p>
                <h2 id="practice-prompt-title">{session.current_turn.prompt}</h2>
                {session.current_turn.wait_sequence.some((step) => step.line) && (
                  <p className="practice-pressure-hint">잠시 뒤 상대방이 재촉할 수 있습니다. 서두르지 말고 확인할 내용을 말해 보세요.</p>
                )}
                <form className="stack" onSubmit={submitAnswer}>
                  <label htmlFor="practice-answer">내 답변</label>
                  <textarea id="practice-answer" value={answer} maxLength={2000} onChange={(event) => setAnswer(event.target.value)} placeholder="예: 이 조건을 계약서에서 먼저 확인하고, 확인되기 전에는 진행하지 않겠습니다." disabled={submitting} />
                  <div className="practice-answer-actions">
                    <button type="button" className="secondary" disabled={submitting} onClick={() => void sendTurn(true)}>답변하지 못했어요</button>
                    <button type="submit" disabled={submitting || !answer.trim()}>{submitting ? "답변 확인 중…" : "답변 보내기"}</button>
                  </div>
                </form>
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
