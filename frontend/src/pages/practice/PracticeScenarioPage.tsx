import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ErrorState, LoadingState } from "../../components/feedback/AsyncState";
import { PageShell } from "../../components/layout/PageShell";
import { practiceService } from "../../services/practiceService";
import type { PracticeScenarioDetailDto } from "../../types/api";

const money = new Intl.NumberFormat("ko-KR");

export function PracticeScenarioPage() {
  const { scenarioId = "" } = useParams();
  const navigate = useNavigate();
  const [scenario, setScenario] = useState<PracticeScenarioDetailDto | null>(null);
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [starting, setStarting] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  async function loadScenario() {
    setStatus("loading");
    try {
      setScenario(await practiceService.getScenario(scenarioId));
      setStatus("success");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "연습 상황을 불러오지 못했습니다.");
      setStatus("error");
    }
  }

  useEffect(() => { void loadScenario(); }, [scenarioId]);

  async function startPractice() {
    setStarting(true);
    setErrorMessage("");
    try {
      const session = await practiceService.createSession(scenarioId);
      navigate(`/practice/sessions/${session.practice_session_id}`);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "연습을 시작하지 못했습니다.");
      setStarting(false);
    }
  }

  return (
    <PageShell layout="workspace" step="계약 연습" title={scenario?.title ?? "연습 상황"} description="계약 상황과 화면에 공개된 문구만 확인한 뒤 대화를 시작하세요." showJourney={false}>
      <div className="stack">
        {status === "loading" && <LoadingState title="연습 상황을 불러오는 중" description="공개 가능한 합성 계약 정보만 준비하고 있습니다." />}
        {status === "error" && <ErrorState title="연습 상황을 불러오지 못했습니다" description={errorMessage} onRetry={() => void loadScenario()} />}
        {status === "success" && scenario && (
          <>
            <div className="practice-labels">
              {scenario.always_show_labels.map((label) => <span key={label}>{label}</span>)}
            </div>
            <section className="practice-contract-card" aria-labelledby="practice-contract-title">
              <h2 id="practice-contract-title">계약 상황</h2>
              <dl className="practice-facts">
                <div><dt>계약 종류</dt><dd>{scenario.synthetic_contract.contract_type}</dd></div>
                <div><dt>보증금</dt><dd>{money.format(scenario.synthetic_contract.deposit)}원</dd></div>
                <div><dt>계약 단계</dt><dd>{scenario.contract_stage}</dd></div>
                <div><dt>대화 상대</dt><dd>{scenario.role}</dd></div>
                <div className="practice-facts__wide practice-facts__wide--aligned"><dt>주택 주소</dt><dd className="practice-facts__address">{scenario.synthetic_contract.property_address}</dd></div>
                <div><dt>등기상 소유자</dt><dd>{scenario.synthetic_contract.owner_names.join(", ")}</dd></div>
                <div><dt>입금 계좌 명의</dt><dd>{scenario.synthetic_contract.account_holder}</dd></div>
              </dl>
            </section>
            <section className="practice-clause-card" aria-labelledby="practice-clause-title">
              <h2 id="practice-clause-title">계약서 특약</h2>
              <ul>{scenario.synthetic_contract.special_clauses.map((clause) => <li key={clause}>{clause}</li>)}</ul>
            </section>
            <section className="practice-prompt-preview" aria-labelledby="practice-first-line-title">
              <p>첫 대화</p>
              <h2 id="practice-first-line-title">{scenario.role}의 말</h2>
              <blockquote>{scenario.initial_turn.prompt}</blockquote>
            </section>
            {errorMessage && <p className="notice" role="alert">{errorMessage}</p>}
            <div className="page-actions">
              <Link className="text-link" to="/practice">다른 상황 선택</Link>
              <button type="button" disabled={starting} onClick={() => void startPractice()}>{starting ? "연습을 준비하는 중…" : "대화 연습 시작"}</button>
            </div>
          </>
        )}
      </div>
    </PageShell>
  );
}
