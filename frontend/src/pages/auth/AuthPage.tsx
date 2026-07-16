import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { PageShell } from "../../components/layout/PageShell";
import { ApiError } from "../../services/apiClient";
import { mvpService } from "../../services/mvpService";

export function AuthPage({ mode }: { mode: "login" | "signup" }) {
  const navigate = useNavigate();
  const [email, setEmail] = useState("demo@lease.test");
  const [error, setError] = useState("");
  const isLogin = mode === "login";

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      await mvpService.authenticate(mode, email);
      navigate("/contracts");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "일시적인 오류가 발생했습니다.");
    }
  }

  return (
    <PageShell step="1 / 8" title={isLogin ? "로그인" : "회원가입"} description="계약 건별로 확인 결과와 체크리스트를 저장합니다." showLogout={false}>
      <form className="stack" onSubmit={submit}>
        <label>이메일<input type="email" value={email} onChange={(e) => setEmail(e.target.value)} /></label>
        <label>비밀번호<input type="password" defaultValue="password123" /></label>
        {error && <p className="error" role="alert">{error}</p>}
        <button type="submit">{isLogin ? "로그인하고 시작" : "가입하고 시작"}</button>
      </form>
      <p className="switch-link">{isLogin ? "계정이 없나요?" : "이미 계정이 있나요?"} <Link to={isLogin ? "/signup" : "/login"}>{isLogin ? "회원가입" : "로그인"}</Link></p>
    </PageShell>
  );
}
