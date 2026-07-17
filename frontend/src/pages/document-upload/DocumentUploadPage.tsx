import { useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { PageShell } from "../../components/layout/PageShell";
import { mvpService } from "../../services/mvpService";
import { contractIdFromRoute } from "../../utils/contractId";

export function DocumentUploadPage() {
  const { contractId: routeContractId } = useParams();
  const contractId = contractIdFromRoute(routeContractId);
  const navigate = useNavigate();
  const [contractFile, setContractFile] = useState<File | null>(null);
  const [registrySource, setRegistrySource] = useState<"mock" | "upload">("mock");
  const [registryFile, setRegistryFile] = useState<File | null>(null);
  const [caseId, setCaseId] = useState("CASE-001");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!contractFile || (registrySource === "upload" && !registryFile)) return;
    setError("");
    setSubmitting(true);
    try {
      await mvpService.uploadDocument(contractId, contractFile, "계약서");
      if (registrySource === "upload" && registryFile) {
        await mvpService.uploadDocument(contractId, registryFile, "등기사항증명서");
      } else {
        await mvpService.linkRegistry(contractId, caseId);
      }
      await mvpService.startExtraction(contractId);
      navigate(`/contracts/${contractId}/review`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "문서 처리 시작에 실패했습니다.");
      setSubmitting(false);
    }
  }

  const ready = Boolean(contractFile) && (registrySource === "mock" ? Boolean(caseId.trim()) : Boolean(registryFile));

  return (
    <PageShell step="4 / 8" title="계약 문서 업로드" description="계약서와 등기 자료를 준비하면 실제 추출을 시작합니다.">
      <form className="stack" onSubmit={submit}>
        <label>계약서 PDF<input type="file" accept="application/pdf,image/jpeg,image/png,.txt" onChange={(event) => setContractFile(event.target.files?.[0] ?? null)} /></label>
        <label>등기 자료<select value={registrySource} onChange={(event) => setRegistrySource(event.target.value as "mock" | "upload")}><option value="mock">모의 등기 연결</option><option value="upload">등기사항증명서 업로드</option></select></label>
        {registrySource === "mock" ? (
          <label>모의 등기 case_id<input required value={caseId} onChange={(event) => setCaseId(event.target.value)} /></label>
        ) : (
          <label>등기사항증명서<input type="file" accept="application/pdf,image/jpeg,image/png,.txt" onChange={(event) => setRegistryFile(event.target.files?.[0] ?? null)} /></label>
        )}
        {error && <p className="error" role="alert">{error}</p>}
        <button type="submit" disabled={!ready || submitting}>{submitting ? "업로드·추출 시작 중…" : "추출 시작하기"}</button>
      </form>
    </PageShell>
  );
}
