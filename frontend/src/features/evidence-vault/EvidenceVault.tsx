import { useState } from "react";
import { mvpService } from "../../services/mvpService";
import { EVIDENCE_DOCUMENT_TYPES, type DocumentDto, type EvidenceDocumentType } from "../../types/api";

const MAX_FILE_SIZE = 20 * 1024 * 1024;
const ALLOWED_EXTENSIONS = [".pdf", ".jpg", ".jpeg", ".png"];

const TYPE_HINTS: Record<EvidenceDocumentType, string> = {
  이체내역: "계약금·잔금 이체확인증, 영수증",
  대화기록: "임대인·공인중개사와 주고받은 문자·메신저 캡처",
  현장사진: "집 상태, 열쇠·도어락 인계, 계량기 사진",
  "기타 증빙": "위임장 사본, 확인서 등 남겨둘 자료",
};

function validationMessage(file: File): string {
  const name = file.name.toLowerCase();
  if (!ALLOWED_EXTENSIONS.some((extension) => name.endsWith(extension))) {
    return "PDF, JPG, JPEG 또는 PNG 파일만 보관할 수 있습니다.";
  }
  if (file.size === 0) return "빈 파일은 보관할 수 없습니다.";
  if (file.size > MAX_FILE_SIZE) return "파일은 20MB 이하여야 합니다.";
  return "";
}

function sizeLabel(bytes: number): string {
  return bytes < 1024 * 1024
    ? `${Math.max(1, Math.round(bytes / 1024))}KB`
    : `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
}

interface EvidenceVaultProps {
  contractId: number;
  documents: DocumentDto[];
  onChange: (documents: DocumentDto[]) => void;
}

/**
 * 증빙 보관함 — 계약서·이체내역·대화기록·사진을 계약 건에 모아 둔다.
 * 분석 입력이 아니라 분쟁 상담·조정 때 제출할 자료라서 판정에 쓰지 않는다.
 */
export function EvidenceVault({ contractId, documents, onChange }: EvidenceVaultProps) {
  const [docType, setDocType] = useState<EvidenceDocumentType>("이체내역");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  function selectFile(selected: File | null) {
    const message = selected ? validationMessage(selected) : "";
    setError(message);
    setFile(message ? null : selected);
  }

  async function upload() {
    if (!file) {
      setError("보관할 파일을 선택해 주세요.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const created = await mvpService.uploadDocument(contractId, file, docType);
      onChange([created, ...documents]);
      setFile(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "증빙을 보관하지 못했습니다.");
    } finally {
      setBusy(false);
    }
  }

  async function download(document_: DocumentDto) {
    setError("");
    try {
      const blob = await mvpService.downloadDocument(contractId, document_.id);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = document_.filename;
      link.click();
      URL.revokeObjectURL(url);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "증빙을 내려받지 못했습니다.");
    }
  }

  async function remove(document_: DocumentDto) {
    if (!window.confirm(`'${document_.filename}'을(를) 보관함에서 삭제할까요?`)) return;
    setError("");
    try {
      await mvpService.deleteDocument(contractId, document_.id);
      onChange(documents.filter((candidate) => candidate.id !== document_.id));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "증빙을 삭제하지 못했습니다.");
    }
  }

  return (
    <section className="history-section evidence-vault" aria-labelledby="evidence-vault-title">
      <div className="checklist-section__head">
        <h2 id="evidence-vault-title">증빙 보관함</h2>
        <span className="checklist-section__count">{documents.length}건 보관</span>
      </div>
      <p className="checklist-section__description">
        이체내역·대화기록·사진을 계약 건에 함께 모아 두면 나중에 상담·조정 자료로 바로 꺼낼 수 있습니다.
        보관한 파일은 서버에 암호화해서 저장하며 판정에는 사용하지 않습니다.
      </p>
      <div className="evidence-vault__form">
        <label className="evidence-vault__field">
          <span>자료 종류</span>
          <select
            value={docType}
            disabled={busy}
            onChange={(event) => setDocType(event.target.value as EvidenceDocumentType)}
          >
            {EVIDENCE_DOCUMENT_TYPES.map((type) => (
              <option key={type} value={type}>{type}</option>
            ))}
          </select>
        </label>
        <label className="evidence-vault__field">
          <span>파일 선택</span>
          <input
            type="file"
            accept={ALLOWED_EXTENSIONS.join(",")}
            disabled={busy}
            onChange={(event) => selectFile(event.target.files?.[0] ?? null)}
          />
        </label>
        <button type="button" disabled={busy || !file} onClick={() => void upload()}>
          {busy ? "보관하는 중…" : "보관함에 넣기"}
        </button>
      </div>
      <p className="evidence-vault__hint">{TYPE_HINTS[docType]}</p>
      {error && <p className="error" role="alert">{error}</p>}
      {documents.length === 0
        ? <p className="checklist-section__empty">아직 보관한 증빙이 없습니다.</p>
        : (
          <ul className="evidence-vault__items">
            {documents.map((item) => (
              <li key={item.id}>
                <div>
                  <span className="evidence-vault__type">{item.doc_type}</span>
                  <strong>{item.filename}</strong>
                  <small>
                    {new Date(item.created_at).toLocaleDateString("ko-KR")} · {sizeLabel(item.size_bytes)}
                  </small>
                </div>
                <div className="evidence-vault__item-actions">
                  <button className="text-button" type="button" onClick={() => void download(item)}>내려받기</button>
                  <button className="text-button" type="button" onClick={() => void remove(item)}>삭제</button>
                </div>
              </li>
            ))}
          </ul>
        )}
    </section>
  );
}
