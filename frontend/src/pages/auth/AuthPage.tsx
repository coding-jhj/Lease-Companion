import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { PageShell } from "../../components/layout/PageShell";
import { ApiError } from "../../services/apiClient";
import { saveAccessToken } from "../../services/authToken";
import { mvpService } from "../../services/mvpService";

export function AuthPage({ mode }: { mode: "login" | "signup" }) {
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const isLogin = mode === "login";

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      if (isLogin) {
        const response = await mvpService.login(username, password);
        saveAccessToken(response.access_token);
        navigate("/choose-mode", { replace: true });
      } else {
        await mvpService.signup(username, email, password);
        navigate("/login", { replace: true });
      }
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "일시적인 오류가 발생했습니다.");
    } finally {
      setSubmitting(false);
    }
  }

  const hero = (
    <>
      <div className="auth-hero__brandline">
        <span className="auth-hero__mark" aria-hidden="true">
          <svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 3l7 3v5c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6l7-3z" />
            <path d="M9 12l2 2 4-4" />
          </svg>
        </span>
        <p className="auth-hero__brand">슬기로운 계약생활</p>
      </div>
      <h2 className="auth-hero__tagline">첫 전월세 계약,<br />혼자 확인하지 마세요</h2>
      <ul className="auth-hero__points">
        <li>계약서·등기 올리면 확인할 항목을 자동 정리</li>
        <li>어려운 특약, 쉬운 말로 설명</li>
        <li>서명 전 체크리스트·물어볼 질문 안내</li>
      </ul>
      <p className="auth-hero__note">비식별·데모 자료만 사용합니다. 안전·사기 여부를 단정하지 않고, 확인할 점을 알려드려요.</p>
    </>
  );

  return (
    <PageShell layout="auth" step="시작" title={isLogin ? "로그인" : "회원가입"} description="계약 건별로 확인 결과와 체크리스트를 저장합니다." showLogout={false} showJourney={false} hero={hero}>
      <form className="stack" onSubmit={submit}>
        <label>아이디<input autoComplete="username" required value={username} onChange={(event) => setUsername(event.target.value)} /></label>
        {!isLogin && <label>이메일<input type="email" autoComplete="email" required value={email} onChange={(event) => setEmail(event.target.value)} /></label>}
        <label>비밀번호<input type="password" autoComplete={isLogin ? "current-password" : "new-password"} required minLength={8} value={password} onChange={(event) => setPassword(event.target.value)} /></label>
        {error && <p className="error" role="alert">{error}</p>}
        <button type="submit" disabled={submitting}>{submitting ? "처리 중…" : isLogin ? "로그인하고 시작" : "회원가입"}</button>
      </form>
      <p className="switch-link">{isLogin ? "계정이 없나요?" : "이미 계정이 있나요?"} <Link to={isLogin ? "/signup" : "/login"}>{isLogin ? "회원가입" : "로그인"}</Link></p>
    </PageShell>
  );
}
