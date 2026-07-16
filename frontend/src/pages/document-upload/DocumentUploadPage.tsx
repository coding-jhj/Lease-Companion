import { useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { PageShell } from "../../components/layout/PageShell";
import { mvpService } from "../../services/mvpService";

export function DocumentUploadPage() {
  const { contractId = "contract-demo-001" } = useParams();
  const navigate = useNavigate();
  const [file, setFile] = useState<File | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!file) return;
    await mvpService.uploadDocument(contractId, file);
    navigate(`/contracts/${contractId}/review`);
  }

  return (
    <PageShell step="5 / 8" title="계약 문서 업로드" description="계약서 PDF는 필수이며 등기사항증명서는 별도로 추가할 수 있습니다.">
      <form className="stack" onSubmit={submit}>
        <label>계약서 PDF<input type="file" accept="application/pdf" onChange={(e) => setFile(e.target.files?.[0] ?? null)} /></label>
        <button type="submit" disabled={!file}>추출값 확인하기</button>
      </form>
    </PageShell>
  );
}
