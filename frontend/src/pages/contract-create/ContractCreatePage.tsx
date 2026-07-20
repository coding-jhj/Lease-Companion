import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { PageShell } from "../../components/layout/PageShell";
import { mvpService } from "../../services/mvpService";

export function ContractCreatePage() {
  const navigate = useNavigate();
  const [title, setTitle] = useState("상도동 전세 계약");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      const contract = await mvpService.createContract(title);
      navigate("/contracts/" + contract.id + "/situation");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "계약을 만들지 못했습니다.");
      setSubmitting(false);
    }
  }

  return (
    <PageShell step="3 / 8" title="계약 건 만들기" description="나중에 알아보기 쉬운 계약 이름을 정하세요.">
      <form className="stack" onSubmit={submit}>
        <label>계약 이름<input value={title} onChange={(e) => setTitle(e.target.value)} /></label>
        {error && <p className="error" role="alert">{error}</p>}
        <button type="submit" disabled={submitting}>{submitting ? "계약 생성 중" : "계약 상황 입력하기"}</button>
      </form>
    </PageShell>
  );
}
