import { Link } from "react-router-dom";
import { PageShell } from "../../components/layout/PageShell";

export function ModeSelectPage() {
  return (
    <PageShell
      layout="workspace"
      step="모드 선택"
      title="현재 어떤 상황인가요?"
      description="지금 가지고 있는 자료와 필요한 도움에 맞춰 선택하세요. 나중에 다른 방법으로 바꿀 수 있습니다."
      showJourney={false}
      eyebrow="슬기로운 계약생활 시작"
    >
      <section className="mode-select-grid" aria-label="이용할 모드 선택">
        <article className="mode-select-card mode-select-card--practice">
          <div className="mode-select-card__heading">
            <span>계약서가 없거나 대화가 걱정될 때</span>
            <h2>먼저 대화를 연습하고 싶어요</h2>
          </div>
          <p>계약서 요약을 읽고 공인중개사·임대인에게 직접 질문하면서 서명 직전 상황을 연습합니다.</p>
          <ul>
            <li>실제 계약서 업로드 없이 시작</li>
            <li>대화 중 특약 다시 확인</li>
            <li>내 질문과 최종 행동 복기</li>
          </ul>
          <Link className="button-link" to="/practice">가상 상황으로 연습하기</Link>
        </article>

        <article className="mode-select-card">
          <div className="mode-select-card__heading">
            <span>계약서 초안을 받은 뒤</span>
            <h2>내 계약서를 확인하고 싶어요</h2>
          </div>
          <p>내 계약 건을 만들고 계약서·등기사항증명서의 확인 항목과 공식 근거를 살펴봅니다.</p>
          <ul>
            <li>현재 계약 진행 상황 입력</li>
            <li>계약서와 가지고 있는 관련 문서 확인</li>
            <li>먼저 확인할 내용과 물어볼 문장 제공</li>
          </ul>
          <Link className="button-link" to="/contracts">내 계약서 점검 시작</Link>
        </article>
      </section>
      <p className="mode-select-help">두 모드는 분리되어 있으며, 선택 후에도 내 계약 화면에서 다른 모드로 이동할 수 있습니다.</p>
    </PageShell>
  );
}
