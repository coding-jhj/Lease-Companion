import { useState } from "react";
import { Link } from "react-router-dom";
import { PageShell } from "../../components/layout/PageShell";

const preparationSections = [
  {
    title: "집을 볼 때",
    items: ["정확한 주소", "집을 보여주는 사람이 누구인지", "보증금·월세·관리비"],
  },
  {
    title: "계약서 초안을 요청할 때",
    script: "서명하기 전에 계약서 내용을 먼저 확인하고 싶습니다. 초안을 보내주실 수 있을까요?",
  },
  {
    title: "가계약금을 보내기 전에",
    items: ["누구에게 보내는 돈인지", "돌려받을 수 있는 조건", "집 주소와 금액"],
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
      step="계약 준비"
      title="계약 전에 세 가지만 준비해 보세요"
      description="계약서를 받기 전에도 확인할 내용과 물어볼 문장을 미리 준비할 수 있어요."
      showJourney={false}
      showLogout={false}
      eyebrow="계약 준비 도움말 · 약 2분"
    >
      <section className="preparation-grid" aria-label="계약 준비 안내">
        {preparationSections.map((section) => (
          <article className="preparation-card" key={section.title}>
            <h2>{section.title}</h2>
            {"items" in section ? (
              <ul>
                {section.items.map((item) => <li key={item}>{item}</li>)}
              </ul>
            ) : (
              <>
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
        <p>로컬 시연에서는 비식별 문서만 사용할 수 있습니다.</p>
        <Link className="button-link" to="/practice">이 상황을 연습해 볼게요</Link>
        <Link className="text-link" to="/contracts/new">계약서 초안을 받았어요</Link>
      </section>
    </PageShell>
  );
}
