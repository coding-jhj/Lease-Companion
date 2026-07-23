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

const financialReviewFields = new Set([
  "account_holder",
  "agent_relationship",
  "balance_payment",
  "balance_payment_date",
  "contract_payment",
  "contract_payment_date",
  "deposit",
  "end_date",
  "landlord_name",
  "management_fee",
  "mortgage_present",
  "move_in_date",
  "owner_names",
  "owner_shares",
  "property_address",
  "senior_claim_amount",
  "trust_present",
]);

const focusedClauseFields = new Set(["special_clauses"]);

function requiresManualReview(view: FieldViewModel, hasDraft: boolean) {
  return focusedClauseFields.has(view.field.field_name)
    || directConfirmationFields.has(view.field.field_name)
    || hasDraft
    || ["not_stated", "not_applicable"].includes(view.field.issue_code ?? "")
    || (
      financialReviewFields.has(view.field.field_name)
      && view.field.confidence === "실패"
    );
}

function canBulkConfirm(view: FieldViewModel) {
  return view.field.confidence !== "실패"
    && !directConfirmationFields.has(view.field.field_name)
    && !focusedClauseFields.has(view.field.field_name);
}

export function ExtractionReviewPage() {
  const { contractId: routeContractId } = useParams();
  const contractId = contractIdFromRoute(routeContractId);
  const navigate = useNavigate();
  const [documents, setDocuments] = useState<DocumentExtractionDto[]>([]);
  const [drafts, setDrafts] = useState<Record<string, DraftValue>>({});
  const [verificationByKey, setVerificationByKey] = useState<Record<string, VerificationStatus>>({});
  const [reviewedKeys, setReviewedKeys] = useState<string[]>([]);
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
      const loadedFields = fieldViewModels(extractedDocuments);
      setVerificationByKey(Object.fromEntries(
        loadedFields.map((view) => [view.key, view.field.verification_status]),
      ));
      setReviewedKeys(loadedFields
        .filter((view) => view.field.verification_status !== "unverified")
        .map((view) => view.key));
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
    setReviewedKeys((current) => current.filter((key) => key !== view.key));
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
    setReviewedKeys((current) => current.filter((key) => key !== view.key));
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
    setReviewedKeys((current) => [...new Set([...current, view.key])]);
    setVerificationByKey((current) => ({
      ...current,
      [view.key]: current[view.key] === "corrected" ? "corrected" : "confirmed",
    }));
  }

  function confirmReadableFields() {
    const readableKeys = fields
      .filter(canBulkConfirm)
      .map((view) => view.key);
    setReviewedKeys((current) => [...new Set([...current, ...readableKeys])]);
    setVerificationByKey((current) => ({
      ...current,
      ...Object.fromEntries(
        fields
          .filter(canBulkConfirm)
          .map((view) => [view.key, drafts[view.key] === undefined ? "confirmed" : "corrected"]),
      ),
    }));
  }

  const pendingCorrectionKeys = Object.keys(drafts).filter((key) => !savedDraftKeys.includes(key));
  const hasUnverified = fields.some(
    (view) => !reviewedKeys.includes(view.key)
      && (
        view.field.confidence !== "실패"
        || requiresManualReview(view, hasDraftInput(view.key))
      ),
  );
  const confirmedFields = fields.filter((view) => reviewedKeys.includes(view.key));
  const unreviewedFields = fields.filter((view) => !reviewedKeys.includes(view.key));
  const readableFields = unreviewedFields.filter((view) => (
    canBulkConfirm(view)
  ));
  const unresolvedFields = unreviewedFields.filter((view) => !readableFields.includes(view));
  const attentionFields = unresolvedFields.filter((view) => (
    requiresManualReview(view, hasDraftInput(view.key))
  ));
  const optionalFailedFields = unresolvedFields.filter((view) => !attentionFields.includes(view));
  const blockingFields = unreviewedFields.filter((view) => (
    view.field.confidence !== "실패"
    || requiresManualReview(view, hasDraftInput(view.key))
  ));
  const unresolvedFinancialFields = unreviewedFields.filter((view) => (
    financialReviewFields.has(view.field.field_name)
    && view.field.confidence === "실패"
  ));
  const specialClauseView = fields.find((view) => (
    view.document_type === "contract" && view.field.field_name === "special_clauses"
  ));
  const specialClauseCount = specialClauseView ? currentClauseValues(specialClauseView).filter((value) => value.trim()).length : 0;
  const warningEntries = [
    ...contractWarnings.map((warning) => ({ document: "계약서", warning })),
    ...registryWarnings.map((warning) => ({ document: "등기사항증명서", warning })),
  ];

  function fieldsForDocument(items: FieldViewModel[], documentType: "contract" | "registry") {
    return items.filter((view) => view.document_type === documentType);
  }

  function renderDocumentFields(
    items: FieldViewModel[],
    documentType: "contract" | "registry",
    title: string,
  ) {
    const documentFields = fieldsForDocument(items, documentType);
    if (documentFields.length === 0) return null;
    return (
      <section className="review-document-group" aria-label={title}>
        <div className="review-document-group__heading">
          <h3>{title}</h3>
          <span>{documentFields.length}개</span>
        </div>
        <div className="review-field-grid">{documentFields.map(renderFieldCard)}</div>
      </section>
    );
  }

  function renderFieldCard(view: FieldViewModel) {
    return (
      <ExtractionFieldCard
        key={view.key}
        view={view}
        draft={drafts[view.key]}
        verification={verificationByKey[view.key] ?? view.field.verification_status}
        reviewed={reviewedKeys.includes(view.key)}
        allowEmptyConfirmation={financialReviewFields.has(view.field.field_name)
          && view.field.confidence === "실패"}
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
    <PageShell layout="workspace" step="5 / 8" title="문서에서 읽은 내용 확인" description="잘못 읽힌 내용이 있으면 고치고, 맞는 내용은 확인해 주세요.">
      <div className="stack">
        {status === "loading" && <LoadingState title="추출 상태를 확인하는 중" description="서버의 최신 추출 실행을 찾고 있습니다." />}
        {status === "processing" && <LoadingState title={runStatus === "pending" ? "추출 대기 중" : "문서에서 값을 추출하는 중"} description="완료될 때까지 실제 처리 상태를 확인하고 있습니다." />}
        {status === "error" && <ErrorState title="추출값을 불러오지 못했습니다" description={errorMessage} retryLabel="문서 다시 올리기" onRetry={() => navigate(`/contracts/${contractId}/upload`)} />}
        {status === "success" && fields.length === 0 && <EmptyState title="확인할 추출값이 없습니다" description="문서를 다시 업로드하거나 처리 상태를 확인해 주세요." />}
        {status === "success" && fields.length > 0 && (
          <section className="review-focus" aria-labelledby="review-focus-title">
            <div className="section-heading">
              <p>모든 내용을 한꺼번에 보지 않고 중요한 세 부분부터 확인합니다</p>
              <h2 id="review-focus-title">이번 단계에서 확인할 내용</h2>
            </div>
            <div className="review-focus__grid">
              <article className="review-focus__card review-focus__card--manual">
                <span>직접 확인</span>
                <h3>표준계약서 서식</h3>
                <strong>직접 확인이 필요해요</strong>
                <p>계약서 첫 장에서 ‘법무부 주택임대차 표준계약서’와 2023.10.6. 개정 표시가 있는지 확인해 주세요.</p>
              </article>
              <article className="review-focus__card review-focus__card--clause">
                <span>반드시 확인</span>
                <h3>특약 원문</h3>
                <strong>{specialClauseCount > 0 ? `${specialClauseCount}개 조항 추출` : "원문 확인 필요"}</strong>
                <p>보증금 반환 조건, 책임 전가, 권리변동 관련 문구가 원문과 같은지 아래에서 확인하세요.</p>
              </article>
              <article className="review-focus__card">
                <span>분석 준비</span>
                <h3>돈과 권리에 관련된 중요 내용</h3>
                <strong>{unresolvedFinancialFields.length > 0 ? `${unresolvedFinancialFields.length}개 확인 필요` : "필요값 추출됨"}</strong>
                <p>금액·지급일·예금주·소유자·근저당 등은 읽지 못한 값만 아래에 표시하고, 실제 관련 신호는 확인 완료 후 분석합니다.</p>
              </article>
            </div>
          </section>
        )}
        {status === "success" && fields.length > 0 && (
          <section className="review-progress" aria-labelledby="review-progress-title">
            <div>
              <p>현재 확인 진행 상황</p>
              <h2 id="review-progress-title">확인이 필요한 값부터 살펴보세요</h2>
            </div>
            <div className="review-progress__actions">
              <div className="review-progress__counts">
                <span><strong>{attentionFields.length}</strong> 직접 확인</span>
                <span><strong>{readableFields.length + optionalFailedFields.length}</strong> 접어둔 항목</span>
                <span><strong>{confirmedFields.length}</strong> 확인 완료</span>
              </div>
              {readableFields.length > 0 && (
                <button className="secondary" type="button" onClick={confirmReadableFields}>읽힌 값 모두 확인</button>
              )}
            </div>
          </section>
        )}
        {status === "success" && warningEntries.length > 0 && (
          <details className="extraction-warnings">
            <summary>문서 처리 안내 {warningEntries.length}건</summary>
            <div>{warningEntries.map(({ document, warning }, index) => (
              <p className="notice" role="status" key={`${document}-warning-${index}`}><strong>{document}</strong> · {warning}</p>
            ))}</div>
          </details>
        )}
        {status === "success" && fields.length > 0 && (
          <section className="attention-review" aria-labelledby="attention-review-title">
            <div className="section-heading">
              <p>특약 원문과 금전피해 분석에 필요한 누락값만 먼저 모았습니다</p>
              <h2 id="attention-review-title">특약·핵심값 확인 {attentionFields.length}개</h2>
            </div>
            {attentionFields.length > 0 ? (
              <div className="review-document-stack">
                {renderDocumentFields(attentionFields, "contract", "계약서")}
                {renderDocumentFields(attentionFields, "registry", "등기사항증명서")}
              </div>
            ) : <p className="group-empty">직접 확인하거나 수정할 항목이 없습니다.</p>}
          </section>
        )}
        {status === "success" && readableFields.length > 0 && (
          <details className="readable-fields">
            <summary>
              <span><strong>문서에서 읽힌 값</strong><small>{readableFields.length}개 · 필요할 때 펼쳐서 수정할 수 있습니다.</small></span>
              <span className="collapse-arrow" aria-hidden="true">▸</span>
            </summary>
            <div className="readable-fields__body">
              <div className="readable-fields__toolbar">
                <p>원문과 맞는지 훑어본 뒤 한 번에 확인할 수 있습니다.</p>
              </div>
              <div className="review-document-stack">
                {renderDocumentFields(readableFields, "contract", "계약서")}
                {renderDocumentFields(readableFields, "registry", "등기사항증명서")}
              </div>
            </div>
          </details>
        )}
        {status === "success" && optionalFailedFields.length > 0 && (
          <details className="readable-fields optional-failed-fields">
            <summary>
              <span><strong>그 밖에 읽지 못한 값</strong><small>{optionalFailedFields.length}개 · 확인할 수 있는 값만 입력해도 됩니다.</small></span>
              <span className="collapse-arrow" aria-hidden="true">▸</span>
            </summary>
            <div className="readable-fields__body">
              <p className="group-empty">현재 문서에서 읽지 못한 값입니다. 분석은 해당 값이 없는 상태로 진행되며, 원문에서 확인되는 경우에만 직접 입력하세요.</p>
              <div className="review-document-stack">
                {renderDocumentFields(optionalFailedFields, "contract", "계약서")}
                {renderDocumentFields(optionalFailedFields, "registry", "등기사항증명서")}
              </div>
            </div>
          </details>
        )}
        {status === "success" && confirmedFields.length > 0 && (
          <details className="confirmed-fields">
            <summary>
              <span>확인된 항목 {confirmedFields.length}개</span>
              <span className="collapse-arrow" aria-hidden="true">▸</span>
            </summary>
            <div className="confirmed-fields__items">
              {confirmedFields.map(renderFieldCard)}
            </div>
          </details>
        )}
        {pendingCorrectionKeys.length > 0 && <p className="unsaved" role="status">저장되지 않은 수정 {pendingCorrectionKeys.length}건</p>}
        {correctionError && <p className="error" role="alert">수정 요청 실패: {correctionError}</p>}
        {confirmationError && <p className="error" role="alert">확인 실패: {confirmationError}</p>}
        {status === "success" && fields.length > 0 && hasUnverified && (
          <p className="notice review-remaining" role="status">
            <span>미확인 필드가 남아 있어 분석을 시작할 수 없습니다.</span>
            <small> 확인이 필요한 항목 {blockingFields.length}개를 완료해 주세요.</small>
          </p>
        )}
        <button type="button" disabled={status !== "success" || fields.length === 0 || hasUnverified || submitting} onClick={() => void confirm()}>
          {submitting ? "확인 내용을 저장하는 중…" : "확인 완료하고 분석하기"}
        </button>
      </div>
    </PageShell>
  );
}
