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
      title="슬기로운 계약생활 시작"
      description="실제 계약을 점검하거나, 계약 상황을 미리 연습할 수 있어요."
      showJourney={false}
      eyebrow=""
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

// 아이콘 path = Phosphor Icons (MIT License) — duotone. shield-check / chats.
function ShieldCheckIcon() {
  return (
    <svg viewBox="0 0 256 256" width="27" height="27" fill="currentColor">
      <path d="M216,56v56c0,96-88,120-88,120S40,208,40,112V56a8,8,0,0,1,8-8H208A8,8,0,0,1,216,56Z" opacity="0.2" />
      <path d="M208,40H48A16,16,0,0,0,32,56v56c0,52.72,25.52,84.67,46.93,102.19,23.06,18.86,46,25.26,47,25.53a8,8,0,0,0,4.2,0c1-.27,23.91-6.67,47-25.53C198.48,196.67,224,164.72,224,112V56A16,16,0,0,0,208,40Zm0,72c0,37.07-13.66,67.16-40.6,89.42A129.3,129.3,0,0,1,128,223.62a128.25,128.25,0,0,1-38.92-21.81C61.82,179.51,48,149.3,48,112l0-56,160,0ZM82.34,141.66a8,8,0,0,1,11.32-11.32L112,148.69l50.34-50.35a8,8,0,0,1,11.32,11.32l-56,56a8,8,0,0,1-11.32,0Z" />
    </svg>
  );
}

function ChatIcon() {
  return (
    <svg viewBox="0 0 256 256" width="27" height="27" fill="currentColor">
      <path d="M224,96V224l-39.58-32H88a8,8,0,0,1-8-8V144h88a8,8,0,0,0,8-8V88h40A8,8,0,0,1,224,96Z" opacity="0.2" />
      <path d="M216,80H184V48a16,16,0,0,0-16-16H40A16,16,0,0,0,24,48V176a8,8,0,0,0,13,6.22L72,154V184a16,16,0,0,0,16,16h93.59L219,230.22a8,8,0,0,0,5,1.78,8,8,0,0,0,8-8V96A16,16,0,0,0,216,80ZM66.55,137.78,40,159.25V48H168v88H71.58A8,8,0,0,0,66.55,137.78ZM216,207.25l-26.55-21.47a8,8,0,0,0-5-1.78H88V152h80a16,16,0,0,0,16-16V96h32Z" />
    </svg>
  );
}
