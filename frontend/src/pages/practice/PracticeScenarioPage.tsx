import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ErrorState, LoadingState } from "../../components/feedback/AsyncState";
import { PageShell } from "../../components/layout/PageShell";
import { practiceService } from "../../services/practiceService";
import type { PracticeScenarioDetailDto } from "../../types/api";
import { PracticeMissionCard } from "./PracticeMissionCard";

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
    <PageShell layout="workspace" step="계약 연습" title="주택임대차계약서 확인" description="계약서 내용을 읽은 뒤 대화 연습을 시작하세요." showJourney={false}>
      <div className="stack">
        {status === "loading" && <LoadingState title="연습 상황을 불러오는 중" description="공개 가능한 합성 계약 정보만 준비하고 있습니다." />}
        {status === "error" && <ErrorState title="연습 상황을 불러오지 못했습니다" description={errorMessage} onRetry={() => void loadScenario()} />}
        {status === "success" && scenario && (
          <>
            <PracticeMissionCard scenarioId={scenario.scenario_id} />
            <section className="practice-contract-card" aria-labelledby="practice-contract-title">
              <h2 id="practice-contract-title">주택임대차계약서</h2>
              <h3 className="practice-contract-card__section-title">계약 내용</h3>
              <dl className="practice-facts">
                <div><dt>계약 종류</dt><dd>{scenario.synthetic_contract.contract_type}</dd></div>
                <div><dt>보증금</dt><dd>{money.format(scenario.synthetic_contract.deposit)}원</dd></div>
                {scenario.synthetic_contract.monthly_rent !== null && (
                  <div><dt>월 차임</dt><dd>{money.format(scenario.synthetic_contract.monthly_rent)}원</dd></div>
                )}
                <div><dt>계약금</dt><dd>{money.format(scenario.synthetic_contract.contract_payment)}원</dd></div>
                <div><dt>잔금</dt><dd>{money.format(scenario.synthetic_contract.balance_payment)}원</dd></div>
                <div className="practice-facts__wide practice-facts__wide--aligned"><dt>주택 주소</dt><dd className="practice-facts__address">{scenario.synthetic_contract.property_address}</dd></div>
                <div><dt>임대인</dt><dd>{scenario.synthetic_contract.landlord_name}</dd></div>
                <div><dt>공인중개사</dt><dd>{scenario.synthetic_contract.broker_name}</dd></div>
                <div><dt>계약 시작일</dt><dd>{scenario.synthetic_contract.start_date}</dd></div>
                <div><dt>계약 종료일</dt><dd>{scenario.synthetic_contract.end_date}</dd></div>
                <div><dt>잔금 지급일</dt><dd>{scenario.synthetic_contract.balance_payment_date}</dd></div>
                <div><dt>입주 예정일</dt><dd>{scenario.synthetic_contract.move_in_date}</dd></div>
                <div><dt>입금 계좌 명의</dt><dd>{scenario.synthetic_contract.account_holder}</dd></div>
              </dl>
              <div className="practice-contract-card__clauses" aria-labelledby="practice-clause-title">
                <h3 id="practice-clause-title">특약사항</h3>
                <ol>{scenario.synthetic_contract.special_clauses.map((clause) => <li key={clause}>{clause}</li>)}</ol>
              </div>
            </section>
            {errorMessage && <p className="notice" role="alert">{errorMessage}</p>}
            <div className="page-actions">
              <Link className="text-link" to="/practice">다른 상황 선택</Link>
              <button type="button" disabled={starting} onClick={() => void startPractice()}>{starting ? "연습을 준비하는 중…" : "계약서 확인 완료 · 대화 시작"}</button>
            </div>
          </>
        )}
      </div>
    </PageShell>
  );
}
