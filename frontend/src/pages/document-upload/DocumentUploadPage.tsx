import { useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { PageShell } from "../../components/layout/PageShell";
import {
  DocumentUploadCard,
  type DocumentUploadStatus,
} from "../../features/document-upload/DocumentUploadCard";
import { mvpService } from "../../services/mvpService";
import type { UploadDocumentType } from "../../types/api";
import { contractIdFromRoute } from "../../utils/contractId";

const MAX_FILE_SIZE = 20 * 1024 * 1024;
const ALLOWED_EXTENSIONS = [".pdf", ".jpg", ".jpeg", ".png"];

type UploadFiles = Record<UploadDocumentType, File | null>;
type UploadStatuses = Record<UploadDocumentType, DocumentUploadStatus>;
type UploadErrors = Record<UploadDocumentType, string>;

const initialFiles: UploadFiles = {
  계약서: null,
  등기사항증명서: null,
  "중개대상물 확인설명서": null,
};
const initialStatuses: UploadStatuses = {
  계약서: "idle",
  등기사항증명서: "idle",
  "중개대상물 확인설명서": "idle",
};
const initialErrors: UploadErrors = {
  계약서: "",
  등기사항증명서: "",
  "중개대상물 확인설명서": "",
};

function fileValidationMessage(file: File): string {
  const lowerName = file.name.toLowerCase();
  if (!ALLOWED_EXTENSIONS.some((extension) => lowerName.endsWith(extension))) {
    return "PDF, JPG, JPEG 또는 PNG 파일만 업로드할 수 있습니다.";
  }
  if (file.size === 0) return "빈 파일은 업로드할 수 없습니다.";
  if (file.size > MAX_FILE_SIZE) return "파일은 20MB 이하여야 합니다.";
  return "";
}

export function DocumentUploadPage() {
  const { contractId: routeContractId } = useParams();
  const contractId = contractIdFromRoute(routeContractId);
  const navigate = useNavigate();
  const [files, setFiles] = useState<UploadFiles>(initialFiles);
  const [statuses, setStatuses] = useState<UploadStatuses>(initialStatuses);
  const [uploadErrors, setUploadErrors] = useState<UploadErrors>(initialErrors);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  function selectFile(docType: UploadDocumentType, file: File | null) {
    const validationError = file ? fileValidationMessage(file) : "";
    setFiles((current) => ({ ...current, [docType]: validationError ? null : file }));
    setStatuses((current) => ({
      ...current,
      [docType]: validationError ? "error" : file ? "ready" : "idle",
    }));
    setUploadErrors((current) => ({ ...current, [docType]: validationError }));
    setError("");
  }

  async function uploadOne(docType: UploadDocumentType): Promise<boolean> {
    const file = files[docType];
    if (!file) return true;
    setStatuses((current) => ({ ...current, [docType]: "uploading" }));
    setUploadErrors((current) => ({ ...current, [docType]: "" }));
    try {
      await mvpService.uploadDocument(contractId, file, docType);
      setStatuses((current) => ({ ...current, [docType]: "success" }));
      return true;
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : "문서를 업로드하지 못했습니다.";
      setStatuses((current) => ({ ...current, [docType]: "error" }));
      setUploadErrors((current) => ({ ...current, [docType]: message }));
      return false;
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!files.계약서) {
      setError("계약서 초안을 올리거나 문서 없이 준비할 내용을 확인해 주세요.");
      return;
    }
    setError("");
    setSubmitting(true);
    const documentTypes = (Object.keys(files) as UploadDocumentType[]).filter((docType) => files[docType]);
    for (const docType of documentTypes) {
      if (statuses[docType] !== "success" && !(await uploadOne(docType))) {
        setSubmitting(false);
        return;
      }
    }
    try {
      await mvpService.startExtraction(contractId);
      navigate(`/contracts/${contractId}/review`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "문서 처리 시작에 실패했습니다.");
      setSubmitting(false);
    }
  }

  return (
    <PageShell layout="narrow" step="4 / 8" title="가지고 있는 문서 올리기" description="계약서는 필요하며, 다른 문서는 가지고 있는 것만 추가하면 됩니다.">
      <form className="stack" onSubmit={submit}>
        <div className="helper-banner">
          <strong>먼저 계약서 초안을 준비해 주세요.</strong>
          <p>등기사항증명서나 확인설명서가 없어도 진행할 수 있습니다. 없는 자료의 내용은 추측하지 않고 ‘확인하지 못함’으로 알려드립니다.</p>
        </div>
        <section className="upload-preparation" aria-labelledby="upload-preparation-title">
          <h2 id="upload-preparation-title">어떤 문서인가요?</h2>
          <ul>
            <li><strong>계약서</strong><span>금액·기간·특약이 적힌 계약서 초안 또는 작성 중인 계약서</span></li>
            <li><strong>등기사항증명서</strong><span>서명 전에 중개사에게 받아볼 수 있습니다.</span></li>
          </ul>
        </section>
        <div className="privacy-notice">
          <span className="privacy-notice__icon" aria-hidden="true">⚠️</span>
          <p>
            <strong>현재 시연용 서비스입니다.</strong>{" "}
            실제 주민등록번호·연락처·계좌번호가 포함된 문서는 올리지 마세요.
            비식별 처리된 문서만 사용해 주세요.
          </p>
        </div>
        <div className="upload-section">
        <p className="file-help" id="upload-file-help">PDF·JPG·JPEG·PNG 파일을 20MB 이하로 올려주세요.</p>
        <div className="upload-card-grid">
          <DocumentUploadCard
            docType="계약서"
            title="계약서"
            description="서명 전에 받은 초안도 가능합니다. 금액·날짜·특약을 확인합니다."
            required
            file={files.계약서}
            status={statuses.계약서}
            error={uploadErrors.계약서}
            disabled={submitting}
            onSelect={(file) => selectFile("계약서", file)}
            onRetry={() => void uploadOne("계약서")}
          />
          <DocumentUploadCard
            docType="등기사항증명서"
            title="등기사항증명서"
            description="소유자와 권리관계를 확인합니다. 지금 없어도 계약서부터 확인할 수 있습니다."
            file={files.등기사항증명서}
            status={statuses.등기사항증명서}
            error={uploadErrors.등기사항증명서}
            disabled={submitting}
            onSelect={(file) => selectFile("등기사항증명서", file)}
            onRetry={() => void uploadOne("등기사항증명서")}
          />
        </div>
        </div>
        {error && <p className="error" role="alert">{error}</p>}
        <button type="submit" disabled={submitting}>{submitting ? "문서를 준비하는 중…" : "업로드하고 다음 단계로"}</button>
      </form>
    </PageShell>
  );
}
