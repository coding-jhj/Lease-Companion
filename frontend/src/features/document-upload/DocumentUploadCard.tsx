import { useRef } from "react";
import type { UploadDocumentType } from "../../types/api";

export type DocumentUploadStatus = "idle" | "ready" | "uploading" | "success" | "error";

const statusLabels: Record<DocumentUploadStatus, string> = {
  idle: "선택 전",
  ready: "업로드 대기",
  uploading: "업로드 중",
  success: "업로드 완료",
  error: "업로드 실패",
};

function UploadIcon() {
  return (
    <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 15V4" />
      <path d="M8 8l4-4 4 4" />
      <path d="M4 15v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3" />
    </svg>
  );
}

function formatFileSize(size: number) {
  if (size < 1024) return `${size}B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)}KB`;
  return `${(size / (1024 * 1024)).toFixed(1)}MB`;
}

export function DocumentUploadCard({
  docType,
  title,
  description,
  required = false,
  file,
  status,
  error,
  disabled = false,
  onSelect,
  onRetry,
}: {
  docType: UploadDocumentType;
  title: string;
  description: string;
  required?: boolean;
  file: File | null;
  status: DocumentUploadStatus;
  error?: string;
  disabled?: boolean;
  onSelect: (file: File | null) => void;
  onRetry?: () => void;
}) {
  const inputId = `document-${docType}`;
  const inputRef = useRef<HTMLInputElement>(null);
  const extension = file?.name.split(".").pop()?.toUpperCase() ?? "";
  const fileSelectionLabel = `${title} ${file ? "다른 파일 선택" : "새 파일 선택"}`;

  return (
    <article className={`upload-card upload-card--${status}${required ? " upload-card--required" : ""}`}>
      <header className="upload-card__header">
        <div>
          <p className={`upload-card__requirement upload-card__requirement--${required ? "required" : "optional"}`}>{required ? "필수 문서" : "선택 문서"}</p>
          <h2>{title}</h2>
        </div>
        <span className={`upload-status upload-status--${status}`}>{statusLabels[status]}</span>
      </header>
      <p className="upload-card__description">{description}</p>
      <input
        className="sr-only"
        ref={inputRef}
        id={inputId}
        aria-label={`${title} 사진 또는 파일 올리기`}
        aria-describedby="upload-file-help"
        type="file"
        tabIndex={-1}
        accept="application/pdf,image/jpeg,image/png"
        disabled={disabled}
        onChange={(event) => onSelect(event.target.files?.[0] ?? null)}
      />
      <label
        className={`file-dropzone${file ? " file-dropzone--filled" : ""}`}
        htmlFor={inputId}
        role="button"
        tabIndex={disabled ? -1 : 0}
        aria-disabled={disabled}
        aria-label={fileSelectionLabel}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            inputRef.current?.click();
          }
        }}
      >
        {file ? (
          <>
            <span className="file-dropzone__doc">
              <span className="file-dropzone__doc-icon" aria-hidden="true">문서</span>
              <span className="file-dropzone__doc-meta">
                <strong>{file.name}</strong>
                <span>{extension || "파일"} · {formatFileSize(file.size)}</span>
              </span>
            </span>
            <span className="file-dropzone__text">다른 파일 선택</span>
          </>
        ) : (
          <>
            <span className="file-dropzone__icon" aria-hidden="true"><UploadIcon /></span>
            <span className="file-dropzone__text">파일 선택하기</span>
            <span className="file-dropzone__hint">클릭해서 PDF·JPG·PNG 올리기</span>
          </>
        )}
      </label>
      {status === "error" && file && onRetry && (
        <button className="secondary" type="button" disabled={disabled} onClick={onRetry}>이 문서 다시 업로드</button>
      )}
      {error && <p className="field-error" role="alert">{error}</p>}
    </article>
  );
}
