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
        navigate("/contracts", { replace: true });
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

  return (
    <PageShell step="1 / 8" title={isLogin ? "로그인" : "회원가입"} description="계약 건별로 확인 결과와 체크리스트를 저장합니다." showLogout={false}>
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
