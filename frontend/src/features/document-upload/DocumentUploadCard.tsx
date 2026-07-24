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

function formatFileSize(size: number) {
  if (size < 1024) return `${size}바이트`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)}킬로바이트`;
  return `${(size / (1024 * 1024)).toFixed(1)}메가바이트`;
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
    <article className={`upload-card upload-card--${status}`}>
      <header className="upload-card__header">
        <div>
          <p className="upload-card__requirement">{required ? "필수 문서" : "선택 문서"}</p>
          <h2>{title}</h2>
        </div>
        <span className={`upload-status upload-status--${status}`}>{statusLabels[status]}</span>
      </header>
      <p className="upload-card__description">{description}</p>
      {file ? (
        <div className="selected-file" aria-label={`${title} 선택 파일`}>
          <span className="selected-file__icon" aria-hidden="true">문서</span>
          <div>
            <strong>{file.name}</strong>
            <span>{extension || "파일"} · {formatFileSize(file.size)}</span>
          </div>
        </div>
      ) : (
        <p className="upload-card__empty">아직 선택한 파일이 없습니다.</p>
      )}
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
      <div className="upload-card__actions">
        <label
          className="file-picker"
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
          {file ? "다른 파일 선택" : "새 파일 선택"}
        </label>
        {status === "error" && file && onRetry && (
          <button className="secondary" type="button" disabled={disabled} onClick={onRetry}>이 문서 다시 업로드</button>
        )}
      </div>
      {error && <p className="field-error" role="alert">{error}</p>}
    </article>
  );
}
