import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { clearAccessToken } from "../../services/authToken";

interface JourneyDisplay {
  current: number;
  currentLabel: string;
  nextLabel?: string;
}

interface PageShellProps {
  step: string;
  journey?: JourneyDisplay;
  title: string;
  description: string;
  children: ReactNode;
  showLogout?: boolean;
  showJourney?: boolean;
  layout?: "auth" | "default" | "narrow" | "workspace" | "report";
  eyebrow?: string;
}

const journeySteps = ["시작 방법", "집 등록", "상황 입력", "문서 준비", "내용 확인", "결과 준비", "확인 결과", "다음 행동"];

export function PageShell({
  step,
  journey,
  title,
  description,
  children,
  showLogout = true,
  showJourney = true,
  layout = "default",
  eyebrow = "첫 계약 확인 도우미",
}: PageShellProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const currentStep = journey?.current ?? Number(step.split("/")[0].trim());
  const showModeSelect = showLogout && location.pathname !== "/choose-mode";
  const currentStepRef = useRef<HTMLDivElement | null>(null);
  const [showFullJourney, setShowFullJourney] = useState(false);

  // 8단계로 늘어난 진행 표시가 좁은 화면에서 가로로 넘칠 때, 현재 단계가 화면 밖에
  // 숨지 않도록 진행 표시 안에서만 가로 스크롤한다. 포커스는 옮기지 않는다.
  useEffect(() => {
    const element = currentStepRef.current;
    if (!element || typeof element.scrollIntoView !== "function") return;
    const reduceMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    try {
      element.scrollIntoView({
        block: "nearest",
        inline: "center",
        behavior: reduceMotion ? "auto" : "smooth",
      });
    } catch {
      // jsdom 등 scrollIntoView 미구현 환경은 무시한다.
    }
  }, [currentStep, showFullJourney]);

  useEffect(() => {
    document.documentElement.scrollTop = 0;
    document.body.scrollTop = 0;
  }, [location.pathname]);

  function logout() {
    clearAccessToken();
    navigate("/login", { replace: true });
  }

  const journeyMap = (
    <nav className="journey-map" aria-label="계약 확인 진행 단계">
      {journeySteps.map((label, index) => {
        const number = index + 1;
        const state = number === currentStep ? "current" : number < currentStep ? "complete" : "upcoming";
        return (
          <div className={`journey-step journey-step--${state}`} ref={state === "current" ? currentStepRef : undefined} aria-current={state === "current" ? "step" : undefined} key={label}>
            <span>{state === "complete" ? "✓" : number}</span>
            <small>{label}</small>
          </div>
        );
      })}
    </nav>
  );

  return (
    <main className={`app-shell app-shell--${layout}`}>
      <header className="app-header">
        <Link className="brand" to="/contracts">슬기로운 계약생활</Link>
        <div className="header-actions">
          <span className="step-badge">{step}</span>
          {showModeSelect && <Link className="mode-switch-link" to="/choose-mode">처음으로</Link>}
          {showLogout && <button className="logout-button" type="button" onClick={logout}>로그아웃</button>}
        </div>
      </header>
      {showJourney && journey && (
        <div className="journey-overview">
          <div className="journey-overview__actions">
            <p>{`현재: ${journey.currentLabel}`}</p>
            {journey.nextLabel && <p>{`다음: ${journey.nextLabel}`}</p>}
          </div>
          <button
            aria-controls="full-journey"
            aria-expanded={showFullJourney}
            className="journey-overview__toggle"
            type="button"
            onClick={() => setShowFullJourney((isOpen) => !isOpen)}
          >
            {showFullJourney ? "전체 과정 접기" : "전체 과정 보기"}
          </button>
          {showFullJourney && <div className="journey-overview__full" id="full-journey">{journeyMap}</div>}
        </div>
      )}
      {showJourney && !journey && journeyMap}
      <section className="page-card">
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p className="description">{description}</p>
        {children}
      </section>
    </main>
  );
}
