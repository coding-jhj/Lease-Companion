import type { ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import { clearAccessToken } from "../../services/authToken";

interface PageShellProps {
  step: string;
  title: string;
  description: string;
  children: ReactNode;
  showLogout?: boolean;
  layout?: "auth" | "default" | "workspace" | "report";
}

const journeySteps = ["시작", "계약", "상황", "문서", "확인", "분석", "리포트", "행동"];

export function PageShell({
  step,
  title,
  description,
  children,
  showLogout = true,
  layout = "default",
}: PageShellProps) {
  const navigate = useNavigate();
  const currentStep = Number(step.split("/")[0].trim());

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
          {showLogout && <button className="logout-button" type="button" onClick={logout}>로그아웃</button>}
        </div>
      </header>
      <nav className="journey-map" aria-label="계약 확인 진행 단계">
        {journeySteps.map((label, index) => {
          const number = index + 1;
          const state = number === currentStep ? "current" : number < currentStep ? "complete" : "upcoming";
          return (
            <div className={`journey-step journey-step--${state}`} aria-current={state === "current" ? "step" : undefined} key={label}>
              <span>{state === "complete" ? "✓" : number}</span>
              <small>{label}</small>
            </div>
          );
        })}
      </nav>
      <section className="page-card">
        <p className="eyebrow">첫 계약 확인 도우미</p>
        <h1>{title}</h1>
        <p className="description">{description}</p>
        {children}
      </section>
    </main>
  );
}
