import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { PageShell } from "../../components/layout/PageShell";
import { mvpService } from "../../services/mvpService";

export function ContractCreatePage() {
  const navigate = useNavigate();
  const [title, setTitle] = useState("");
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
    <PageShell step="3 / 8" title="확인할 집 등록하기" description="주소 전체를 적지 않아도 됩니다. 나중에 구분하기 쉬운 이름을 붙여 주세요.">
      <form className="stack" onSubmit={submit}>
        <label>
          <span className="field-label">계약 이름<small>예: 신림동 원룸 전세, 학교 앞 월세</small></span>
          <input required placeholder="집을 구분할 이름을 입력하세요" value={title} onChange={(e) => setTitle(e.target.value)} />
        </label>
        {error && <p className="error" role="alert">{error}</p>}
        <button type="submit" disabled={submitting}>{submitting ? "저장하는 중" : "다음: 내 상황 알려주기"}</button>
      </form>
    </PageShell>
  );
}
