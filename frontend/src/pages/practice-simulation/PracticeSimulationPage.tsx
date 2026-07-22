import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";
import { PracticeShell } from "../../components/layout/PracticeShell";
import { PracticeContractSummary } from "../../features/practice-simulation/PracticeContractSummary";
import { classifyPracticeAnswer, practiceService } from "../../services/practiceService";
import type {
  PracticeFinalAction,
  PracticeMessage,
  PracticeObservation,
  PracticePhase,
  PracticeScenario,
} from "../../types/practice";

const initialObservations: PracticeObservation = {
  askedMeaning: false,
  askedNoSuccessor: false,
  askedReturnDate: false,
  requestedRevision: false,
};

const phaseCopy: Record<PracticePhase, { title: string; description: string }> = {
  intro: { title: "서명 직전 대화를 연습해 보세요", description: "평범해 보이는 계약서를 읽고, 필요한 질문을 직접 찾아 말하는 연습입니다." },
  contract: { title: "계약서 요약 확인", description: "특약을 포함한 계약 내용을 천천히 읽어보세요. 대화 중에도 다시 확인할 수 있습니다." },
  dialogue: { title: "공인중개사·임대인과 대화", description: "정답 선택지 없이 궁금하거나 확인할 내용을 직접 입력하세요." },
  action: { title: "서명 전 최종 행동", description: "연습 상황에서 지금 취할 행동을 선택하세요. 서비스가 계약 체결을 권하는 단계는 아닙니다." },
  debrief: { title: "내 대화 복기", description: "점수 대신 실제로 말한 내용과 놓친 확인 행동을 함께 살펴봅니다." },
};

function ObservationRow({ done, label, evidence }: { done: boolean; label: string; evidence?: string }) {
  return (
    <li className={`practice-review-item practice-review-item--${done ? "done" : "missed"}`}>
      <span aria-hidden="true">{done ? "✓" : "○"}</span>
      <div><strong>{label}</strong>{evidence && <small>사용자 발화: “{evidence}”</small>}</div>
    </li>
  );
}

export function PracticeSimulationPage() {
  const [scenario, setScenario] = useState<PracticeScenario | null>(null);
  const [phase, setPhase] = useState<PracticePhase>("intro");
  const [contractReviewed, setContractReviewed] = useState(false);
  const [answer, setAnswer] = useState("");
  const [messages, setMessages] = useState<PracticeMessage[]>([]);
  const [observations, setObservations] = useState(initialObservations);
  const [evidence, setEvidence] = useState<Partial<Record<keyof PracticeObservation, string>>>({});
  const [finalAction, setFinalAction] = useState<PracticeFinalAction | null>(null);
  const [revisionConfirmed, setRevisionConfirmed] = useState(false);

  useEffect(() => { void practiceService.getSigningScenario().then(setScenario); }, []);

  if (!scenario) {
    return <PracticeShell phase="intro" title="연습을 준비하고 있습니다" description="승인된 합성 시나리오를 불러오는 중입니다."><p className="notice">잠시만 기다려 주세요.</p></PracticeShell>;
  }

  const copy = phaseCopy[phase];
  const userMessages = messages.filter((message) => message.speaker === "사용자");

  function beginDialogue() {
    setMessages([{ id: "opening", speaker: "공인중개사", text: scenario!.openingLine }]);
    setPhase("dialogue");
  }

  function submitAnswer(event: FormEvent) {
    event.preventDefault();
    const text = answer.trim();
    if (!text) return;
    const result = classifyPracticeAnswer(text);
    const messageNumber = messages.length + 1;
    setMessages((current) => [
      ...current,
      { id: `user-${messageNumber}`, speaker: "사용자", text },
      { id: `reply-${messageNumber}`, speaker: result.speaker, text: result.response },
    ]);
    setObservations((current) => ({ ...current, ...result.observations }));
    setEvidence((current) => {
      const next = { ...current };
      for (const key of Object.keys(result.observations) as Array<keyof PracticeObservation>) {
        if (result.observations[key] && !next[key]) next[key] = text;
      }
      return next;
    });
    setAnswer("");
  }

  function finish(action: PracticeFinalAction) {
    setFinalAction(action);
    if (action === "특약 수정을 다시 요구") {
      setPhase("action");
      return;
    }
    setPhase("debrief");
  }

  function restart() {
    setPhase("intro");
    setContractReviewed(false);
    setAnswer("");
    setMessages([]);
    setObservations(initialObservations);
    setEvidence({});
    setFinalAction(null);
    setRevisionConfirmed(false);
  }

  return (
    <PracticeShell phase={phase} title={copy.title} description={copy.description}>
      <div className="practice-labels" aria-label="시나리오 안내">
        {scenario.labels.map((label) => <span key={label}>{label}</span>)}
      </div>

      {phase === "intro" && (
        <section className="practice-intro">
          <div className="practice-situation">
            <p>{scenario.situation}</p>
            <p>{scenario.instruction}</p>
          </div>
          <button type="button" onClick={() => setPhase("contract")}>계약서 확인하기</button>
        </section>
      )}

      {phase === "contract" && (
        <div className="stack">
          <PracticeContractSummary contract={scenario.contract} />
          {!contractReviewed ? (
            <button type="button" onClick={() => setContractReviewed(true)}>계약서 확인 완료</button>
          ) : (
            <div className="practice-start-panel">
              <p>계약서는 대화 화면에서도 계속 열어볼 수 있습니다.</p>
              <button type="button" onClick={beginDialogue}>시뮬레이션 시작</button>
            </div>
          )}
        </div>
      )}

      {phase === "dialogue" && (
        <div className="practice-workspace">
          <aside>
            <details open>
              <summary>계약서 요약 다시 보기</summary>
              <PracticeContractSummary compact contract={scenario.contract} />
            </details>
          </aside>
          <section className="practice-dialogue" aria-label="계약 대화">
            <div className="practice-avatar" role="img" aria-label="합성 공인중개사 아바타 영상 자리">
              <span>합성 아바타</span>
              <strong>{messages.at(-1)?.speaker === "사용자" ? "상대방이 듣는 중" : `${messages.at(-1)?.speaker ?? "공인중개사"} 말하기`}</strong>
              <small>영상 연결 영역 · 현재는 자막 중심 MVP</small>
            </div>
            <ol className="practice-transcript" aria-live="polite">
              {messages.map((message) => (
                <li className={`practice-message practice-message--${message.speaker === "사용자" ? "user" : "counterparty"}`} key={message.id}>
                  <strong>{message.speaker}</strong><p>{message.text}</p>
                </li>
              ))}
            </ol>
            <form className="practice-answer" onSubmit={submitAnswer}>
              <label htmlFor="practice-answer">직접 질문하거나 요청하기</label>
              <textarea id="practice-answer" value={answer} onChange={(event) => setAnswer(event.target.value)} placeholder="예: 확인하고 싶은 내용을 직접 입력하세요." />
              <button type="submit" disabled={!answer.trim()}>말하기</button>
            </form>
            <button className="secondary" type="button" onClick={() => setPhase("action")}>대화를 마치고 최종 행동 선택</button>
          </section>
        </div>
      )}

      {phase === "action" && !finalAction && (
        <div className="practice-actions">
          <button type="button" onClick={() => finish("현재 조건으로 계약 체결")}>현재 조건으로 계약 체결</button>
          <button type="button" onClick={() => finish("특약 수정을 다시 요구")}>특약 수정을 다시 요구</button>
          <button className="secondary" type="button" onClick={() => finish("계약 보류")}>계약 보류</button>
          <button className="practice-back" type="button" onClick={() => setPhase("dialogue")}>대화로 돌아가기</button>
        </div>
      )}

      {phase === "action" && finalAction === "특약 수정을 다시 요구" && (
        <section className="practice-revision">
          <p>다음은 연습용 수정 요청 문구입니다. 실제 계약에서는 상대방과 합의해 계약서에 반영하고 서명 여부를 확인해야 합니다.</p>
          <blockquote>{scenario.suggestedRevision}</blockquote>
          <button type="button" onClick={() => { setRevisionConfirmed(true); setObservations((current) => ({ ...current, requestedRevision: true })); setPhase("debrief"); }}>이 문구로 수정 요구 완료</button>
        </section>
      )}

      {phase === "debrief" && (
        <div className="practice-debrief">
          <section className="practice-debrief__summary">
            <p>최종 선택</p><strong>{finalAction}</strong>
            <span>이 결과는 계약의 안전·위험 여부나 체결 권고가 아니라 연습 행동의 복기입니다.</span>
          </section>
          <section>
            <h2>대화에서 확인한 행동</h2>
            <ul className="practice-review-list">
              <ObservationRow done={observations.askedMeaning} label="조건부 반환 특약의 의미를 질문했다" evidence={evidence.askedMeaning} />
              <ObservationRow done={observations.askedNoSuccessor} label="후임 임차인이 구해지지 않는 상황을 질문했다" evidence={evidence.askedNoSuccessor} />
              <ObservationRow done={observations.askedReturnDate} label="보증금의 정확한 반환 시점을 확인했다" evidence={evidence.askedReturnDate} />
              <ObservationRow done={observations.requestedRevision || revisionConfirmed} label="구두 설명에 그치지 않고 특약 수정을 요청했다" evidence={evidence.requestedRevision} />
              <ObservationRow done={finalAction === "계약 보류" || finalAction === "특약 수정을 다시 요구"} label="확인이 끝나기 전 서명 여부를 다시 판단했다" />
            </ul>
          </section>
          <section>
            <h2>실제 사용자 발화</h2>
            {userMessages.length ? <ul className="practice-utterances">{userMessages.map((message) => <li key={message.id}>“{message.text}”</li>)}</ul> : <p className="notice">질문 없이 최종 행동을 선택했습니다. 다시 연습하면서 특약의 의미와 반환 시점을 직접 물어보세요.</p>}
          </section>
          <section className="practice-next-phrase">
            <h2>다음에 사용할 수 있는 문장</h2>
            <p>“후임 임차인 입주 여부와 관계없이 계약 종료일에 보증금을 반환하는 내용으로 특약을 수정해 주세요.”</p>
          </section>
          <div className="page-actions">
            <button type="button" onClick={restart}>같은 상황 다시 연습</button>
            <Link className="button-link secondary" to="/contracts">내 계약으로 돌아가기</Link>
          </div>
        </div>
      )}
    </PracticeShell>
  );
}
