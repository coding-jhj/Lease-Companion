import type { ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import { clearAccessToken } from "../../services/authToken";
import type { PracticePhase } from "../../types/practice";

const steps: Array<{ phase: PracticePhase; label: string }> = [
  { phase: "intro", label: "상황" },
  { phase: "contract", label: "계약서" },
  { phase: "dialogue", label: "대화" },
  { phase: "action", label: "선택" },
  { phase: "debrief", label: "복기" },
];

export function PracticeShell({ phase, title, description, children }: {
  phase: PracticePhase;
  title: string;
  description: string;
  children: ReactNode;
}) {
  const navigate = useNavigate();
  const current = steps.findIndex((step) => step.phase === phase);

  function logout() {
    clearAccessToken();
    navigate("/login", { replace: true });
  }

  return (
    <main className="app-shell app-shell--workspace practice-shell">
      <header className="app-header">
        <Link className="brand" to="/contracts">슬기로운 계약생활</Link>
        <div className="header-actions">
          <span className="practice-label">가상 연습</span>
          <button className="logout-button" type="button" onClick={logout}>로그아웃</button>
        </div>
      </header>
      <nav className="practice-journey" aria-label="계약 연습 진행 단계">
        {steps.map((step, index) => (
          <div className={`practice-journey__step practice-journey__step--${index === current ? "current" : index < current ? "complete" : "upcoming"}`} aria-current={index === current ? "step" : undefined} key={step.phase}>
            <span>{index < current ? "✓" : index + 1}</span><small>{step.label}</small>
          </div>
        ))}
      </nav>
      <section className="page-card">
        <p className="eyebrow">계약 연습 시뮬레이션 모드</p>
        <h1>{title}</h1>
        <p className="description">{description}</p>
        {children}
      </section>
    </main>
  );
}
