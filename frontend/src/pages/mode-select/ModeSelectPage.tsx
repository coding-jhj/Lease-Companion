import { Link } from "react-router-dom";
import { PageShell } from "../../components/layout/PageShell";

const modeOptions = [
  {
    title: "실전 계약 점검",
    description: "내 실제 계약서·상황을 확인할게요",
    to: "/start",
    variant: "",
    icon: <ShieldCheckIcon />,
    points: ["등기부와 계약서 교차검증", "확인할 위험 신호 리포트"],
  },
  {
    title: "계약 연습 시뮬레이션",
    description: "가상 임대인·중개사와 대화를 연습할게요",
    to: "/practice",
    variant: "mode-select-card--practice",
    icon: <ChatIcon />,
    points: ["가상 중개사와 실시간 대화", "내 답변 복기·피드백"],
  },
];

export function ModeSelectPage() {
  return (
    <PageShell
      layout="narrow"
      step="시작"
      title="어떻게 시작할까요?"
      description="실제 계약을 점검하거나, 계약 상황을 미리 연습할 수 있어요."
      showJourney={false}
      showLogout={false}
      eyebrow="슬기로운 계약생활 시작"
    >
      <section className="mode-select-grid" aria-label="모드 선택">
        {modeOptions.map((option) => (
          <Link className={`mode-select-card ${option.variant}`.trim()} to={option.to} key={option.to}>
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

function ShieldCheckIcon() {
  return (
    <svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 3l7 3v5c0 4.5-3 7.6-7 9-4-1.4-7-4.5-7-9V6l7-3z" />
      <path d="M9 12l2 2 4-4" />
    </svg>
  );
}

function ChatIcon() {
  return (
    <svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 4h16a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-7l-5 4v-4H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z" />
      <path d="M8 9h8M8 12h5" />
    </svg>
  );
}
