import type { ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import { clearAccessToken } from "../../services/authToken";

interface PageShellProps {
  step: string;
  title: string;
  description: string;
  children: ReactNode;
  showLogout?: boolean;
}

export function PageShell({ step, title, description, children, showLogout = true }: PageShellProps) {
  const navigate = useNavigate();

  function logout() {
    clearAccessToken();
    navigate("/login", { replace: true });
  }

  return (
    <main className="app-shell">
      <header className="app-header">
        <Link className="brand" to="/contracts">슬기로운 계약생활</Link>
        <div className="header-actions">
          <span className="step-badge">{step}</span>
          {showLogout && <button className="logout-button" type="button" onClick={logout}>로그아웃</button>}
        </div>
      </header>
      <section className="page-card">
        <p className="eyebrow">첫 계약 확인 도우미</p>
        <h1>{title}</h1>
        <p className="description">{description}</p>
        {children}
      </section>
    </main>
  );
}
