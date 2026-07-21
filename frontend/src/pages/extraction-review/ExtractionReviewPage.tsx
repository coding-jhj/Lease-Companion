import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { EmptyState, ErrorState, LoadingState } from "../../components/feedback/AsyncState";
import { PageShell } from "../../components/layout/PageShell";
import { ExtractionFieldCard } from "../../features/extraction-review/ExtractionFieldCard";
import { clauseValues, correctionValue, fieldViewModels } from "../../features/extraction-review/viewModel";
import { mvpService } from "../../services/mvpService";
import type {
  CorrectionRequestDto,
  DocumentExtractionDto,
  FieldViewModel,
  SchemaVersion,
  VerificationStatus,
} from "../../types/api";
import { contractIdFromRoute } from "../../utils/contractId";
import { PollTimeoutError, pollUntilTerminal } from "../../utils/pollUntilTerminal";

type DraftValue = string | string[];

const directConfirmationFields = new Set([
  "guarantee_eligibility_confirmed",
  "lessor_sublease_authority_confirmed",
]);

export function ExtractionReviewPage() {
  const { contractId: routeContractId } = useParams();
  const contractId = contractIdFromRoute(routeContractId);
  const navigate = useNavigate();
  const [documents, setDocuments] = useState<DocumentExtractionDto[]>([]);
  const [drafts, setDrafts] = useState<Record<string, DraftValue>>({});
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
  const contractWarnings = documents.find((document) => document.document_type === "contract")?.warnings ?? [];
  const registryWarnings = documents.find((document) => document.document_type === "registry")?.warnings ?? [];
  const schemaVersion: SchemaVersion = documents.find(
    (document) => document.document_type === "contract",
  )?.schema_version ?? documents[0]?.schema_version ?? "1.8.0";

  function hasDraftInput(key: string): boolean {
    const draft = drafts[key];
    return Array.isArray(draft)
      ? draft.some((item) => item.trim().length > 0)
      : Boolean(draft?.trim());
  }

  function currentClauseValues(view: FieldViewModel): string[] {
    const draft = drafts[view.key];
    return Array.isArray(draft) ? draft : clauseValues(view.field);
  }

  async function loadExtraction() {
    activePoll.current?.abort();
    const controller = new AbortController();
    activePoll.current = controller;
    setStatus("loading");
    try {
      const initialResponse = await mvpService.getLatestExtraction(contractId, controller.signal);
      if (controller.signal.aborted) return;
      const response = await pollUntilTerminal({
        initialValue: initialResponse,
        poll: () => mvpService.getLatestExtraction(contractId, controller.signal),
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

  function updateClauseDraft(view: FieldViewModel, nextValues: string[]) {
    setSavedDraftKeys((current) => current.filter((key) => key !== view.key));
    if (JSON.stringify(nextValues) === JSON.stringify(clauseValues(view.field))) {
      setDrafts((current) => {
        const next = { ...current };
        delete next[view.key];
        return next;
      });
      setVerificationByKey((current) => ({ ...current, [view.key]: view.field.verification_status }));
      return;
    }
    setDrafts((current) => ({ ...current, [view.key]: nextValues }));
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
          .filter((view) => view.field.confidence !== "실패" || hasDraftInput(view.key))
          .map((view) => [view.key, drafts[view.key] === undefined ? "confirmed" : "corrected"]),
      ),
    }));
  }

  const pendingCorrectionKeys = Object.keys(drafts).filter((key) => !savedDraftKeys.includes(key));
  const hasUnverified = fields.some(
    (view) => (view.field.confidence !== "실패" || directConfirmationFields.has(view.field.field_name))
      && (verificationByKey[view.key] ?? view.field.verification_status) === "unverified",
  );
  const confirmedHighConfidenceFields = fields.filter((view) => (
    view.field.confidence === "추출됨"
    && (verificationByKey[view.key] ?? view.field.verification_status) !== "unverified"
  ));
  const attentionFields = fields.filter((view) => !confirmedHighConfidenceFields.includes(view));

  function renderFieldCard(view: FieldViewModel) {
    return (
      <ExtractionFieldCard
        key={view.key}
        view={view}
        draft={drafts[view.key]}
        verification={verificationByKey[view.key] ?? view.field.verification_status}
        onValueChange={(value) => updateField(view, value)}
        onClauseChange={(values) => updateClauseDraft(view, values)}
        onConfirm={() => confirmField(view)}
      />
    );
  }

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
        schema_version: schemaVersion,
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
    <PageShell layout="workspace" step="5 / 8" title="추출값 확인·수정" description="분석 전에 문서에서 읽은 값이 맞는지 직접 확인하세요.">
      <div className="stack">
        {status === "loading" && <LoadingState title="추출 상태를 확인하는 중" description="서버의 최신 추출 실행을 찾고 있습니다." />}
        {status === "processing" && <LoadingState title={runStatus === "pending" ? "추출 대기 중" : "문서에서 값을 추출하는 중"} description="완료될 때까지 실제 처리 상태를 확인하고 있습니다." />}
        {status === "error" && <ErrorState title="추출값을 불러오지 못했습니다" description={errorMessage} retryLabel="문서 다시 올리기" onRetry={() => navigate(`/contracts/${contractId}/upload`)} />}
        {status === "success" && fields.length === 0 && <EmptyState title="확인할 추출값이 없습니다" description="문서를 다시 업로드하거나 처리 상태를 확인해 주세요." />}
        {status === "success" && fields.length > 0 && (
          <button className="secondary" type="button" onClick={confirmReadableFields}>읽힌 값 모두 확인</button>
        )}
        {status === "success" && fields.length > 0 && (
          <div className="extraction-workspace-grid">
            <section className="document-review-panel" aria-labelledby="contract-fields-title">
              <h2 id="contract-fields-title">계약서 추출값</h2>
              <p className="section-description">불확실하거나 아직 확인하지 않은 값을 먼저 보여드립니다.</p>
              {contractWarnings.map((warning, index) => (
                <p className="notice" role="status" key={`contract-warning-${index}`}>{warning}</p>
              ))}
              <div className="stack">
                {attentionFields.some((view) => view.document_type === "contract")
                  ? attentionFields.filter((view) => view.document_type === "contract").map(renderFieldCard)
                  : <p className="group-empty">지금 확인할 계약서 항목이 없습니다.</p>}
              </div>
            </section>
            <section className="document-review-panel" aria-labelledby="registry-fields-title">
              <h2 id="registry-fields-title">등기사항증명서 추출값</h2>
              <p className="section-description">불확실하거나 아직 확인하지 않은 값을 먼저 보여드립니다.</p>
              {registryWarnings.map((warning, index) => (
                <p className="notice" role="status" key={`registry-warning-${index}`}>{warning}</p>
              ))}
              <div className="stack">
                {attentionFields.some((view) => view.document_type === "registry")
                  ? attentionFields.filter((view) => view.document_type === "registry").map(renderFieldCard)
                  : <p className="group-empty">지금 확인할 등기 항목이 없습니다.</p>}
              </div>
            </section>
          </div>
        )}
        {status === "success" && confirmedHighConfidenceFields.length > 0 && (
          <details className="confirmed-fields">
            <summary>
              <span>확인된 항목 {confirmedHighConfidenceFields.length}개</span>
              <span className="collapse-arrow" aria-hidden="true">▸</span>
            </summary>
            <div className="confirmed-fields__items">
              {confirmedHighConfidenceFields.map(renderFieldCard)}
            </div>
          </details>
        )}
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
