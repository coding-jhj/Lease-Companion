import { useState } from "react";
import { Link } from "react-router-dom";
import { PageShell } from "../../components/layout/PageShell";

const preparationSections = [
  {
    title: "집을 볼 때 유의할 점",
    description: "사진이나 설명만 믿지 말고 현장에서 직접 확인하고 기록해 두세요.",
    items: [
      "계약할 집의 정확한 주소와 동·호수",
      "누수·곰팡이·결로·침수 흔적",
      "보일러·수압·배수·창문·문 상태",
      "관리비 포함 항목과 별도 비용",
      "소음·채광·악취와 주변 환경",
      "하자 사진과 수리 약속을 문자로 기록",
    ],
  },
  {
    title: "가계약하기 전에 자료 요청",
    description: "가계약금을 보내기 전에 다음 자료를 먼저 요청하세요.",
    requestItems: [
      "등기사항증명서",
      "계약서 초안 사본",
      "특약사항",
    ],
    warningTitle: "주의할 점",
    warnings: [
      "가계약금도 계약 성립 여부와 반환 조건을 둘러싼 분쟁이 생길 수 있어요. 송금 전에 반환 조건을 문자나 문서로 남기세요.",
      "\"일단 가계약금부터 넣고 서류는 나중에 보자\"는 요청을 받으면, 자료와 조건을 확인할 때까지 송금을 보류하세요.",
    ],
    script: "가계약금을 보내기 전에 확인하고 싶습니다. 등기사항증명서, 계약서 초안 사본, 특약사항을 먼저 보내주실 수 있을까요?",
  },
  {
    title: "가계약금을 보내기 전에 확인하기",
    description: "계약이 무산됐을 때 돈을 돌려받지 못하는 분쟁을 줄여요.",
    items: [
      "받는 사람과 등기상 소유자의 관계",
      "대상 주택 주소·금액·계약 조건",
      "계약이 무산될 경우 반환 조건을 문자나 문서로 남기기",
    ],
  },
] as const;

export function ContractPreparationPage() {
  const [copyMessage, setCopyMessage] = useState<"success" | "error" | null>(null);
  const requestSection = preparationSections[1];

  async function copyRequest() {
    if (!("script" in requestSection) || !navigator.clipboard) {
      setCopyMessage("error");
      return;
    }

    try {
      await navigator.clipboard.writeText(requestSection.script);
      setCopyMessage("success");
    } catch {
      setCopyMessage("error");
    }
  }

  return (
    <PageShell
      layout="workspace"
      step="실전 계약 점검"
      title="계약 전, 금전 피해와 분쟁을 줄이는 준비"
      description="집을 볼 때부터 계약금을 보내기 전까지 꼭 확인할 내용을 차례대로 살펴보세요."
      showJourney={false}
      showLogout={false}
      eyebrow="실전 계약 점검 · 계약서 초안 없음"
    >
      <section className="beginner-guide" aria-label="계약 준비 안내">
        <strong>급하게 결정하지 않아도 괜찮아요</strong>
        <p>확인하지 못한 내용이 있다면 계약서 작성이나 송금 전에 중개사·임대인에게 먼저 물어보세요.</p>
      </section>
      <section className="preparation-grid" aria-label="계약 준비 안내">
        {preparationSections.map((section) => (
          <article className="preparation-card" key={section.title}>
            <h2>{section.title}</h2>
            <p>{section.description}</p>
            {"items" in section ? (
              <ul>
                {section.items.map((item) => <li key={item}>{item}</li>)}
              </ul>
            ) : (
              <>
                <ul>
                  {section.requestItems.map((item) => <li key={item}>{item}</li>)}
                </ul>
                <aside className="preparation-warning" aria-labelledby="preparation-warning-title">
                  <h3 id="preparation-warning-title">{section.warningTitle}</h3>
                  <ul>
                    {section.warnings.map((warning) => <li key={warning}>{warning}</li>)}
                  </ul>
                </aside>
                <p className="preparation-script">{section.script}</p>
                <button type="button" onClick={copyRequest}>문구 복사</button>
                {copyMessage === "success" && <p role="status">요청 문장을 복사했습니다.</p>}
                {copyMessage === "error" && <p role="alert">문장을 복사하지 못했습니다. 직접 선택해 복사해 주세요.</p>}
              </>
            )}
          </article>
        ))}
      </section>
      <section className="preparation-actions" aria-label="다음 단계">
        <div className="preparation-actions__heading">
          <h2>다음에 무엇을 해볼까요?</h2>
        </div>
        <div className="preparation-action-grid">
          <article className="preparation-action-card">
            <span className="preparation-action-card__label">실전 계약 점검</span>
            <h3>자료를 준비했어요</h3>
            <p>계약서 초안 등 준비한 자료를 올리고 확인할 내용을 점검해 보세요.</p>
            <Link className="button-link" to="/contracts/new">계약서 초안 등을 받아 점검해 보기</Link>
          </article>
          <article className="preparation-action-card preparation-action-card--practice">
            <span className="preparation-action-card__label">계약 연습</span>
            <h3>계약 상황을 먼저 연습하고 싶어요</h3>
            <p>가상 중개사와 대화하면서 질문·확인·거절하는 방법을 연습해 보세요.</p>
            <Link className="button-link preparation-action-card__practice-link" to="/practice">계약할 때 시뮬레이션 체험하러 가기</Link>
          </article>
        </div>
      </section>
    </PageShell>
  );
}
