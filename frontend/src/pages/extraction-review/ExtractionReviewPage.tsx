import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { PageShell } from "../../components/layout/PageShell";
import { mvpService } from "../../services/mvpService";
import type { ExtractedField } from "../../types/api";

export function ExtractionReviewPage() {
  const { contractId = "contract-demo-001" } = useParams();
  const navigate = useNavigate();
  const [fields, setFields] = useState<ExtractedField[]>([]);
  useEffect(() => { void mvpService.getExtraction(contractId).then(setFields); }, [contractId]);

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
        {fields.map((field, index) => (
          <label className="field-card" key={field.fieldName}>{field.label}<span className="confidence">{field.confidence}</span><input value={field.userCorrectedValue ?? field.extractedValue ?? ""} onChange={(e) => updateField(index, e.target.value)} /><small>{field.evidence.page ? `${field.evidence.page}쪽 · ` : ""}{field.evidence.text}</small></label>
        ))}
        <button type="button" onClick={confirm}>확인 완료하고 분석하기</button>
      </div>
    </PageShell>
  );
}
