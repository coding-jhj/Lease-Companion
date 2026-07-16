import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { EmptyState, ErrorState, LoadingState } from "../../components/feedback/AsyncState";
import { PageShell } from "../../components/layout/PageShell";
import { mvpService } from "../../services/mvpService";
import type { ExtractedField } from "../../types/api";

export function ExtractionReviewPage() {
  const { contractId = "contract-demo-001" } = useParams();
  const navigate = useNavigate();
  const [fields, setFields] = useState<ExtractedField[]>([]);
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [errorMessage, setErrorMessage] = useState("");

  async function loadExtraction() {
    setStatus("loading");
    try {
      setFields(await mvpService.getExtraction(contractId));
      setStatus("success");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "추출값을 불러오지 못했습니다.");
      setStatus("error");
    }
  }

  useEffect(() => { void loadExtraction(); }, [contractId]);

  function updateField(index: number, value: string) {
    setFields((current) => current.map((field, i) => i === index ? { ...field, userCorrectedValue: value, verificationStatus: "corrected" } : field));
  }

  async function confirm() {
    await mvpService.confirmExtraction(contractId, fields.map((field) => field.verificationStatus === "unverified" ? { ...field, verificationStatus: "confirmed" } : field));
    navigate(`/contracts/${contractId}/analyzing`);
  }

  return (
    <PageShell step="6 / 8" title="추출값 확인·수정" description="분석 전에 문서에서 읽은 값이 맞는지 직접 확인하세요.">
      <div className="stack">
        {status === "loading" && <LoadingState title="추출값을 불러오는 중" description="계약서에서 읽은 내용을 준비하고 있습니다." />}
        {status === "error" && <ErrorState title="추출값을 불러오지 못했습니다" description={errorMessage} onRetry={() => void loadExtraction()} />}
        {status === "success" && fields.length === 0 && <EmptyState title="확인할 추출값이 없습니다" description="문서를 다시 업로드하거나 처리 상태를 확인해 주세요." />}
        {status === "success" && fields.map((field, index) => (
          <label className="field-card" key={field.fieldName}>{field.label}<span className="confidence">{field.confidence}</span><input value={field.userCorrectedValue ?? field.extractedValue ?? ""} onChange={(e) => updateField(index, e.target.value)} /><small>{field.evidence.page ? `${field.evidence.page}쪽 · ` : ""}{field.evidence.text}</small></label>
        ))}
        <button type="button" disabled={status !== "success" || fields.length === 0} onClick={confirm}>확인 완료하고 분석하기</button>
      </div>
    </PageShell>
  );
}
