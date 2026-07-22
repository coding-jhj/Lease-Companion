import { Link } from "react-router-dom";
import { PageShell } from "../../components/layout/PageShell";

export function ModeSelectPage() {
  return (
    <PageShell
      layout="workspace"
      step="모드 선택"
      title="어떤 방식으로 시작할까요?"
      description="실제 계약서를 점검하거나, 가상 계약 상황에서 서명 직전 대화를 먼저 연습할 수 있습니다."
      showJourney={false}
      eyebrow="슬기로운 계약생활 시작"
    >
      <section className="mode-select-grid" aria-label="이용할 모드 선택">
        <article className="mode-select-card mode-select-card--practice">
          <div className="mode-select-card__heading">
            <span>가상 연습 · 합성 시나리오</span>
            <h2>계약 연습 시뮬레이션</h2>
          </div>
          <p>계약서 요약을 읽고 공인중개사·임대인에게 직접 질문하면서 서명 직전 상황을 연습합니다.</p>
          <ul>
            <li>실제 계약서 업로드 없이 시작</li>
            <li>대화 중 특약 다시 확인</li>
            <li>내 질문과 최종 행동 복기</li>
          </ul>
          <Link className="button-link" to="/practice/signing">연습 시뮬레이션 시작</Link>
        </article>

        <article className="mode-select-card">
          <div className="mode-select-card__heading">
            <span>실제 문서 분석</span>
            <h2>실전 계약 점검</h2>
          </div>
          <p>내 계약 건을 만들고 계약서·등기사항증명서의 확인 항목과 공식 근거를 살펴봅니다.</p>
          <ul>
            <li>계약 상황 입력</li>
            <li>계약서와 관련 문서 업로드</li>
            <li>확인 질문과 방어 리포트 제공</li>
          </ul>
          <Link className="button-link" to="/contracts">실전 계약 점검 시작</Link>
        </article>
      </section>
      <p className="mode-select-help">두 모드는 분리되어 있으며, 선택 후에도 내 계약 화면에서 다른 모드로 이동할 수 있습니다.</p>
    </PageShell>
  );
}
