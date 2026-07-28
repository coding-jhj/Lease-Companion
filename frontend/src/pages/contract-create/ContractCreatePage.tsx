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
    const normalizedTitle = title.trim();
    setError("");
    if (!normalizedTitle) {
      setError("나중에 알아볼 수 있도록 계약 이름을 입력해 주세요.");
      return;
    }
    setSubmitting(true);
    try {
      const contract = await mvpService.createContract(normalizedTitle);
      navigate("/contracts/" + contract.id + "/upload");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "계약을 만들지 못했습니다.");
      setSubmitting(false);
    }
  }

  return (
    <PageShell layout="narrow" step="2 / 7" title="확인할 집 등록하기" description="여러 계약을 구분할 계약 이름만 적어 주세요.">
      <form className="stack" onSubmit={submit}>
        <label>
          <span className="field-label">계약 이름<small>예: 신림동 원룸 전세, 학교 앞 월세</small></span>
          <input placeholder="예: 신림동 원룸 전세" value={title} onChange={(e) => setTitle(e.target.value)} />
        </label>
        {error && <p className="error" role="alert">{error}</p>}
        <button type="submit" disabled={submitting}>{submitting ? "저장하는 중" : "다음: 문서 올리기"}</button>
      </form>
    </PageShell>
  );
}
