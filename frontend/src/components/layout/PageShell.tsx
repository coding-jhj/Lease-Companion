import { useEffect, useRef, type ReactNode } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { clearAccessToken } from "../../services/authToken";

interface PageShellProps {
  step: string;
  title: string;
  description: string;
  children: ReactNode;
  showLogout?: boolean;
  showJourney?: boolean;
  layout?: "auth" | "default" | "workspace" | "report";
  eyebrow?: string;
}

const journeySteps = ["시작 방법", "집 등록", "상황 입력", "문서 준비", "내용 확인", "결과 준비", "확인 결과", "다음 행동"];

export function PageShell({
  step,
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
  const currentStep = Number(step.split("/")[0].trim());
  const showModeSelect = showLogout && location.pathname !== "/choose-mode";
  const currentStepRef = useRef<HTMLDivElement | null>(null);

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
  }, [currentStep]);

  function logout() {
    clearAccessToken();
    navigate("/login", { replace: true });
  }

  return (
    <main className={`app-shell app-shell--${layout}`}>
      <header className="app-header">
        <Link className="brand" to="/contracts">슬기로운 계약생활</Link>
        <div className="header-actions">
          <span className="step-badge">{step}</span>
          {showModeSelect && <Link className="mode-switch-link" to="/choose-mode">모드 선택</Link>}
          {showLogout && <button className="logout-button" type="button" onClick={logout}>로그아웃</button>}
        </div>
      </header>
      {showJourney && <nav className="journey-map" aria-label="계약 확인 진행 단계">
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
      </nav>}
      <section className="page-card">
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p className="description">{description}</p>
        {children}
      </section>
    </main>
  );
}
