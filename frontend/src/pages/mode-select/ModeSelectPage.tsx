import { Link } from "react-router-dom";
import { PageShell } from "../../components/layout/PageShell";

const situationOptions = [
  {
    title: "아직 계약서를 받지 않았어요",
    description: "집을 보거나 계약을 준비 중이에요",
    to: "/prepare",
  },
  {
    title: "계약서 초안을 받았어요",
    description: "서명하기 전에 내용을 확인하고 싶어요",
    to: "/contracts/new",
  },
  {
    title: "이미 계약했어요",
    description: "계약 후 챙길 일을 확인하고 싶어요",
    to: "/contracts",
  },
] as const;

export function ModeSelectPage() {
  return (
    <PageShell
      layout="workspace"
      step="시작"
      title="지금 어떤 상황인가요?"
      description="현재 상황을 알려주시면 먼저 확인할 내용을 안내해 드립니다."
      showJourney={false}
      showLogout={false}
      eyebrow="슬기로운 계약생활 시작"
    >
      <section className="mode-select-grid" aria-label="현재 상황 선택">
        {situationOptions.map((option) => (
          <Link className="mode-select-card" to={option.to} key={option.to}>
            <div className="mode-select-card__heading">
              <h2>{option.title}</h2>
            </div>
            <p>{option.description}</p>
          </Link>
        ))}
      </section>
    </PageShell>
  );
}
