import { Link } from "react-router-dom";
import { PageShell } from "../../components/layout/PageShell";

const situationOptions = [
  {
    title: "아직 계약서를 받지 않았어요",
    description: "집을 보거나 계약을 준비 중이에요",
    to: "/prepare",
    icon: <HouseIcon />,
    points: ["집 볼 때 확인할 항목", "가계약금 전 물어볼 질문"],
  },
  {
    title: "계약서 초안을 받았어요",
    description: "서명하기 전에 내용을 확인하고 싶어요",
    to: "/contracts/new",
    icon: <DocumentIcon />,
    points: ["문서 업로드·추출값 확인", "위험 신호·확인 리포트"],
  },
];

export function SituationSelectPage() {
  return (
    <PageShell
      layout="narrow"
      step="실전 계약 점검"
      title="지금 어떤 상황인가요?"
      description="현재 상황을 알려주시면 먼저 확인할 내용을 안내해 드립니다."
      showJourney={false}
      showLogout={false}
      eyebrow="실전 계약 점검"
    >
      <Link className="text-link mode-select-back" to="/choose-mode">← 모드 다시 선택</Link>
      <section className="mode-select-grid" aria-label="현재 상황 선택">
        {situationOptions.map((option) => (
          <Link className="mode-select-card" to={option.to} key={option.to}>
            <span className="mode-select-card__icon" aria-hidden="true">{option.icon}</span>
            <div className="mode-select-card__heading">
              <h2>{option.title}</h2>
              <p className="mode-select-card__desc">{option.description}</p>
            </div>
            <ul className="mode-select-card__points">
              {option.points.map((point) => <li key={point}>{point}</li>)}
            </ul>
            <span className="mode-select-card__cta">시작하기 →</span>
          </Link>
        ))}
      </section>
    </PageShell>
  );
}

function HouseIcon() {
  return (
    <svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 10.5L12 3l9 7.5" />
      <path d="M5 9.5V20h14V9.5" />
      <path d="M10 20v-5h4v5" />
    </svg>
  );
}

function DocumentIcon() {
  return (
    <svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M13 3H6v18h12V8l-5-5z" />
      <path d="M13 3v5h5" />
      <path d="M9 13h6M9 16h6" />
    </svg>
  );
}
