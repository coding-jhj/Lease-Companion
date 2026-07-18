import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { EmptyState, ErrorState, LoadingState } from "../../components/feedback/AsyncState";
import { PageShell } from "../../components/layout/PageShell";
import { correctionValue, fieldViewModels } from "../../features/extraction-review/viewModel";
import { mvpService } from "../../services/mvpService";
import type {
  CorrectionRequestDto,
  DocumentExtractionDto,
  FieldViewModel,
  VerificationStatus,
} from "../../types/api";
import { contractIdFromRoute } from "../../utils/contractId";
import { PollTimeoutError, pollUntilTerminal } from "../../utils/pollUntilTerminal";

const verificationLabels: Record<VerificationStatus, string> = {
  unverified: "미확인",
  confirmed: "확인됨",
  corrected: "수정됨",
};

export function ExtractionReviewPage() {
  const { contractId: routeContractId } = useParams();
  const contractId = contractIdFromRoute(routeContractId);
  const navigate = useNavigate();
  const [documents, setDocuments] = useState<DocumentExtractionDto[]>([]);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [verificationByKey, setVerificationByKey] = useState<Record<string, VerificationStatus>>({});
  const [savedDraftKeys, setSavedDraftKeys] = useState<string[]>([]);
  const [status, setStatus] = useState<"loading" | "processing" | "success" | "error">("loading");
  const [runStatus, setRunStatus] = useState<"pending" | "running">("pending");
  const [errorMessage, setErrorMessage] = useState("");
  const [correctionError, setCorrectionError] = useState("");
  const [confirmationError, setConfirmationError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const activePoll = useRef<AbortController | null>(null);
  const fields = fieldViewModels(documents);

  async function loadExtraction() {
    activePoll.current?.abort();
    const controller = new AbortController();
    activePoll.current = controller;
    setStatus("loading");
    try {
      const initialResponse = await mvpService.getLatestExtraction(contractId);
      if (controller.signal.aborted) return;
      const response = await pollUntilTerminal({
        initialValue: initialResponse,
        poll: () => mvpService.getLatestExtraction(contractId),
        signal: controller.signal,
        onUpdate: (current) => {
          if (current.status === "pending" || current.status === "running") {
            setRunStatus(current.status);
            setStatus("processing");
          }
        },
      });
      if (response.status === "failed") throw new Error(response.error ?? "문서 추출에 실패했습니다.");
      const extractedDocuments = [response.contract_doc, response.registry_doc].filter(
        (document): document is DocumentExtractionDto => document !== null,
      );
      setDocuments(extractedDocuments);
      setDrafts({});
      setSavedDraftKeys([]);
      setVerificationByKey(Object.fromEntries(
        fieldViewModels(extractedDocuments).map((view) => [view.key, view.field.verification_status]),
      ));
      setStatus("success");
    } catch (error) {
      if (controller.signal.aborted || (error instanceof DOMException && error.name === "AbortError")) return;
      setErrorMessage(error instanceof PollTimeoutError
        ? error.message
        : error instanceof Error ? error.message : "추출값을 불러오지 못했습니다.");
      setStatus("error");
    }
  }

  useEffect(() => {
    void loadExtraction();
    return () => activePoll.current?.abort();
  }, [contractId]);

  function updateField(view: FieldViewModel, value: string) {
    setSavedDraftKeys((current) => current.filter((key) => key !== view.key));
    if (value === view.formattedValue) {
      setDrafts((current) => {
        const next = { ...current };
        delete next[view.key];
        return next;
      });
      setVerificationByKey((current) => ({ ...current, [view.key]: view.field.verification_status }));
      return;
    }
    setDrafts((current) => ({ ...current, [view.key]: value }));
    setVerificationByKey((current) => ({ ...current, [view.key]: "corrected" }));
  }

  function confirmField(view: FieldViewModel) {
    setVerificationByKey((current) => ({ ...current, [view.key]: "confirmed" }));
  }

  function confirmReadableFields() {
    setVerificationByKey((current) => ({
      ...current,
      ...Object.fromEntries(
        fields
          .filter((view) => view.field.confidence !== "실패" || drafts[view.key]?.trim())
          .map((view) => [view.key, drafts[view.key] === undefined ? "confirmed" : "corrected"]),
      ),
    }));
  }

  const pendingCorrectionKeys = Object.keys(drafts).filter((key) => !savedDraftKeys.includes(key));
  const hasUnverified = fields.some(
    (view) => (verificationByKey[view.key] ?? view.field.verification_status) === "unverified",
  );

  async function confirm() {
    setCorrectionError("");
    setConfirmationError("");
    setSubmitting(true);

    if (pendingCorrectionKeys.length > 0) {
      const corrections = pendingCorrectionKeys.map((key) => {
        const view = fields.find((item) => item.key === key)!;
        return {
          document_type: view.document_type,
          field_name: view.field.field_name,
          corrected_value: correctionValue(drafts[key], view.field, view.document_type),
        };
      });
      const request: CorrectionRequestDto = {
        schema_version: "1.2.0",
        contract_id: contractId,
        corrections,
      };
      try {
        await mvpService.submitCorrections(request);
        setSavedDraftKeys((current) => [...new Set([...current, ...pendingCorrectionKeys])]);
      } catch (error) {
        setCorrectionError(error instanceof Error ? error.message : "수정 내용을 저장하지 못했습니다.");
        setSubmitting(false);
        return;
      }
    }

    try {
      await mvpService.confirmExtraction(contractId);
      navigate("/contracts/" + contractId + "/analyzing");
    } catch (error) {
      setConfirmationError(error instanceof Error ? error.message : "추출값 확인을 완료하지 못했습니다.");
      setSubmitting(false);
    }
  }

  return (
    <PageShell step="5 / 8" title="추출값 확인·수정" description="분석 전에 문서에서 읽은 값이 맞는지 직접 확인하세요.">
      <div className="stack">
        {status === "loading" && <LoadingState title="추출 상태를 확인하는 중" description="서버의 최신 추출 실행을 찾고 있습니다." />}
        {status === "processing" && <LoadingState title={runStatus === "pending" ? "추출 대기 중" : "문서에서 값을 추출하는 중"} description="완료될 때까지 실제 처리 상태를 확인하고 있습니다." />}
        {status === "error" && <ErrorState title="추출값을 불러오지 못했습니다" description={errorMessage} onRetry={() => void loadExtraction()} />}
        {status === "success" && fields.length === 0 && <EmptyState title="확인할 추출값이 없습니다" description="문서를 다시 업로드하거나 처리 상태를 확인해 주세요." />}
        {status === "success" && fields.length > 0 && (
          <button className="secondary" type="button" onClick={confirmReadableFields}>읽힌 값 모두 확인</button>
        )}
        {status === "success" && fields.map((view) => {
          const verification = verificationByKey[view.key] ?? view.field.verification_status;
          const locationUnknown = view.field.source_evidence.page === null || view.field.source_evidence.text === null;
          const failedWithoutInput = view.field.confidence === "실패" && !drafts[view.key]?.trim();
          return (
            <article className="field-card" key={view.key}>
              <div className="field-card__meta">
                <strong>{view.label}</strong>
                <span className={"confidence confidence--" + view.field.confidence}>{view.field.confidence}</span>
                <span className={"verification verification--" + verification}>{verificationLabels[verification]}</span>
              </div>
              <label>
                <span className="sr-only">{view.label} 값</span>
                <input
                  aria-label={view.label + " 값"}
                  value={drafts[view.key] ?? view.formattedValue}
                  placeholder={view.field.confidence === "실패" ? "직접 입력해 주세요" : undefined}
                  onChange={(event) => updateField(view, event.target.value)}
                />
              </label>
              {view.field.failure_reason && <p className="field-error">{view.field.failure_reason}</p>}
              <small>{locationUnknown ? "원문 위치 미확인" : view.field.source_evidence.page + "쪽 · " + view.field.source_evidence.text}</small>
              <button className="text-button" type="button" disabled={verification !== "unverified" || failedWithoutInput} onClick={() => confirmField(view)}>이 값 확인</button>
            </article>
          );
        })}
        {pendingCorrectionKeys.length > 0 && <p className="unsaved" role="status">저장되지 않은 수정 {pendingCorrectionKeys.length}건</p>}
        {correctionError && <p className="error" role="alert">수정 요청 실패: {correctionError}</p>}
        {confirmationError && <p className="error" role="alert">확인 실패: {confirmationError}</p>}
        {status === "success" && fields.length > 0 && hasUnverified && (
          <p className="notice" role="status">미확인 필드가 남아 있어 분석을 시작할 수 없습니다.</p>
        )}
        <button type="button" disabled={status !== "success" || fields.length === 0 || hasUnverified || submitting} onClick={() => void confirm()}>
          {submitting ? "확인 내용을 저장하는 중…" : "확인 완료하고 분석하기"}
        </button>
      </div>
    </PageShell>
  );
}
