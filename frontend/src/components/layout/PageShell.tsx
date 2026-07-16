import type { ReactNode } from "react";
import { Link } from "react-router-dom";

interface PageShellProps {
  step: string;
  title: string;
  description: string;
  children: ReactNode;
}

export function PageShell({ step, title, description, children }: PageShellProps) {
  return (
    <main className="app-shell">
      <header className="app-header">
        <Link className="brand" to="/contracts">슬기로운 계약생활</Link>
        <span className="step-badge">{step}</span>
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
