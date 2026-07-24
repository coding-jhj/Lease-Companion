import { Fragment, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { EmptyState, ErrorState, LoadingState } from "../../components/feedback/AsyncState";
import { PageShell } from "../../components/layout/PageShell";
import { GuidedReviewCard } from "../../features/extraction-review/GuidedReviewCard";
import {
  buildReviewQueue,
  type ReviewQueueItem,
} from "../../features/extraction-review/reviewQueue";
import {
  clauseValues,
  correctionValue,
  fieldViewModels,
  splitClauseText,
} from "../../features/extraction-review/viewModel";
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
type CannotVerifyReason = "not_stated" | "unreadable" | "unknown_location";

const reasonLabels: Record<CannotVerifyReason, string> = {
  not_stated: "문서에 적혀 있지 않음",
  unreadable: "글자가 흐려 확인하기 어려움",
  unknown_location: "확인할 위치를 찾기 어려움",
};

function displayViewValue(view: FieldViewModel, drafts: Record<string, DraftValue>): string {
  const draft = drafts[view.key];
  if (Array.isArray(draft)) return draft.join(" · ");
  if (typeof draft === "string") return draft;
  return view.formattedValue || "문서에서 읽은 내용이 없습니다.";
}

function displayValue(item: ReviewQueueItem, drafts: Record<string, DraftValue>): string {
  return displayViewValue(item.view, drafts);
}

// 전체 내용 보기: 긴 조항 원문은 아코디언으로 분리, 나머지는 도메인별 카드로 묶는다.
const CLAUSE_FIELDS = new Set([
  "deposit_return_clause", "repair_responsibility_clause", "main_clauses", "special_clauses",
]);

const REVIEW_DOMAINS: Array<{ key: string; title: string }> = [
  { key: "parties", title: "계약 당사자·목적물" },
  { key: "money", title: "금액" },
  { key: "schedule", title: "기간·일정" },
  { key: "rights", title: "권리·등기" },
  { key: "terms", title: "책임·특약" },
  { key: "etc", title: "기타" },
];

const REVIEW_DOMAIN_BY_FIELD: Record<string, string> = {
  landlord_name: "parties", tenant_name: "parties", agent_name: "parties",
  agent_relationship: "parties", proxy_authority_documents: "parties", property_address: "parties",
  owner_names: "parties", owner_shares: "parties", is_joint_ownership: "parties",
  building_use: "parties", lessor_sublease_authority_confirmed: "parties",
  deposit: "money", deposit_korean_amount: "money", contract_payment: "money",
  contract_payment_korean_amount: "money", balance_payment: "money",
  balance_payment_korean_amount: "money", monthly_rent: "money", monthly_rent_korean_amount: "money",
  management_fee: "money", management_fee_items: "money", management_fee_present: "money",
  account_holder: "money", account_number: "money", bank_name: "money",
  start_date: "schedule", end_date: "schedule", move_in_date: "schedule",
  contract_payment_date: "schedule", balance_payment_date: "schedule", issue_date: "schedule",
  mortgage_present: "rights", seizure_present: "rights", provisional_seizure_present: "rights",
  trust_present: "rights", ground_right_present: "rights", senior_claim_amount: "rights",
  rights_change_clause_present: "rights", violation_building: "rights",
  estimated_housing_value: "rights", guarantee_eligibility_confirmed: "rights",
  deposit_return_condition: "terms", repair_responsibility: "terms", special_clauses_present: "terms",
};

export function ExtractionReviewPage() {
  const { contractId: routeContractId } = useParams();
  const contractId = contractIdFromRoute(routeContractId);
  const navigate = useNavigate();
  const [documents, setDocuments] = useState<DocumentExtractionDto[]>([]);
  const [drafts, setDrafts] = useState<Record<string, DraftValue>>({});
  const [, setVerificationByKey] = useState<Record<string, VerificationStatus>>({});
  const [reviewedKeys, setReviewedKeys] = useState<string[]>([]);
  const [savedDraftKeys, setSavedDraftKeys] = useState<string[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [unresolvedReasonByKey, setUnresolvedReasonByKey] = useState<
    Record<string, CannotVerifyReason>
  >({});
  const [status, setStatus] = useState<"loading" | "processing" | "success" | "error">("loading");
  const [runStatus, setRunStatus] = useState<"pending" | "running">("pending");
  const [errorMessage, setErrorMessage] = useState("");
  const [correctionError, setCorrectionError] = useState("");
  const [confirmationError, setConfirmationError] = useState("");
  const [analysisError, setAnalysisError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [extractionConfirmed, setExtractionConfirmed] = useState(false);
  const [confirmedInputSnapshotId, setConfirmedInputSnapshotId] = useState<string | null>(null);
  const [analysisStartUncertain, setAnalysisStartUncertain] = useState(false);
  const activePoll = useRef<AbortController | null>(null);

  const fields = fieldViewModels(documents);
  const queue = buildReviewQueue(fields);
  const currentItem = queue[currentIndex] ?? null;
  const completedCount = queue.filter((item) => reviewedKeys.includes(item.key)).length;
  const reviewedItems = queue.filter((item) => reviewedKeys.includes(item.key));
  const unresolvedItems = queue.filter((item) => unresolvedReasonByKey[item.key] !== undefined);
  const pendingCorrectionKeys = Object.keys(drafts).filter(
    (key) => !savedDraftKeys.includes(key),
  );
  const schemaVersion: SchemaVersion = documents.find(
    (document) => document.document_type === "contract",
  )?.schema_version ?? documents[0]?.schema_version ?? "1.8.0";

  async function loadExtraction() {
    activePoll.current?.abort();
    const controller = new AbortController();
    activePoll.current = controller;
    setStatus("loading");
    setErrorMessage("");

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
      if (response.status === "failed") {
        throw new Error(response.error ?? "문서 추출에 실패했습니다.");
      }

      const extractedDocuments = [response.contract_doc, response.registry_doc].filter(
        (document): document is DocumentExtractionDto => document !== null,
      );
      const loadedFields = fieldViewModels(extractedDocuments);
      const loadedReviewedKeys = loadedFields
        .filter((view) => view.field.verification_status !== "unverified")
        .map((view) => view.key);
      const loadedQueue = buildReviewQueue(loadedFields);
      const firstUnverifiedIndex = loadedQueue.findIndex(
        (item) => !loadedReviewedKeys.includes(item.key),
      );
      setDocuments(extractedDocuments);
      setDrafts({});
      setSavedDraftKeys([]);
      setCurrentIndex(firstUnverifiedIndex === -1 ? loadedQueue.length : firstUnverifiedIndex);
      setUnresolvedReasonByKey({});
      setExtractionConfirmed(false);
      setConfirmedInputSnapshotId(null);
      setAnalysisStartUncertain(false);
      setCorrectionError("");
      setConfirmationError("");
      setAnalysisError("");
      setVerificationByKey(Object.fromEntries(
        loadedFields.map((view) => [view.key, view.field.verification_status]),
      ));
      setReviewedKeys(loadedReviewedKeys);
      setStatus("success");
    } catch (error) {
      if (
        controller.signal.aborted
        || (error instanceof DOMException && error.name === "AbortError")
      ) {
        return;
      }
      setErrorMessage(error instanceof PollTimeoutError
        ? error.message
        : error instanceof Error ? error.message : "문서에서 읽은 내용을 불러오지 못했습니다.");
      setStatus("error");
    }
  }

  useEffect(() => {
    void loadExtraction();
    return () => activePoll.current?.abort();
  }, [contractId]);

  function updateField(view: FieldViewModel, value: string) {
    const wasSaved = savedDraftKeys.includes(view.key);
    setSavedDraftKeys((current) => current.filter((key) => key !== view.key));
    if (value === view.formattedValue) {
      if (wasSaved) {
        setDrafts((current) => ({ ...current, [view.key]: value }));
        setVerificationByKey((current) => ({ ...current, [view.key]: "corrected" }));
        return;
      }
      setDrafts((current) => {
        const next = { ...current };
        delete next[view.key];
        return next;
      });
      setVerificationByKey((current) => ({
        ...current,
        [view.key]: view.field.verification_status,
      }));
      return;
    }
    setDrafts((current) => ({ ...current, [view.key]: value }));
    setVerificationByKey((current) => ({ ...current, [view.key]: "corrected" }));
  }

  function updateClauseDraft(view: FieldViewModel, nextValues: string[]) {
    const wasSaved = savedDraftKeys.includes(view.key);
    setSavedDraftKeys((current) => current.filter((key) => key !== view.key));
    if (JSON.stringify(nextValues) === JSON.stringify(clauseValues(view.field))) {
      if (wasSaved) {
        setDrafts((current) => ({ ...current, [view.key]: nextValues }));
        setVerificationByKey((current) => ({ ...current, [view.key]: "corrected" }));
        return;
      }
      setDrafts((current) => {
        const next = { ...current };
        delete next[view.key];
        return next;
      });
      setVerificationByKey((current) => ({
        ...current,
        [view.key]: view.field.verification_status,
      }));
      return;
    }
    setDrafts((current) => ({ ...current, [view.key]: nextValues }));
    setVerificationByKey((current) => ({ ...current, [view.key]: "corrected" }));
  }

  function advanceToNextUnreviewed() {
    setCurrentIndex((index) => {
      const nextIndex = queue.findIndex((item, candidateIndex) => (
        candidateIndex > index && !reviewedKeys.includes(item.key)
      ));
      return nextIndex === -1 ? queue.length : nextIndex;
    });
  }

  function markReviewed(item: ReviewQueueItem) {
    setReviewedKeys((current) => [...new Set([...current, item.key])]);
    setVerificationByKey((current) => ({
      ...current,
      [item.key]: current[item.key] === "corrected" ? "corrected" : "confirmed",
    }));
    setUnresolvedReasonByKey((current) => {
      const next = { ...current };
      delete next[item.key];
      return next;
    });
    advanceToNextUnreviewed();
  }

  function changeCurrent(item: ReviewQueueItem, value: string | string[]) {
    setExtractionConfirmed(false);
    setAnalysisStartUncertain(false);
    if (Array.isArray(value)) {
      updateClauseDraft(item.view, value);
    } else {
      updateField(item.view, value);
    }
    setReviewedKeys((current) => [...new Set([...current, item.key])]);
    setVerificationByKey((current) => ({
      ...current,
      [item.key]: current[item.key] === "corrected" ? "corrected" : "confirmed",
    }));
    setUnresolvedReasonByKey((current) => {
      const next = { ...current };
      delete next[item.key];
      return next;
    });
    advanceToNextUnreviewed();
  }

  function markCannotVerify(item: ReviewQueueItem, reason: CannotVerifyReason) {
    setReviewedKeys((current) => current.filter((key) => key !== item.key));
    setUnresolvedReasonByKey((current) => ({ ...current, [item.key]: reason }));
    advanceToNextUnreviewed();
  }

  function fieldTitle(view: FieldViewModel) {
    return queue.find((item) => item.key === view.key)?.title ?? view.label;
  }

  function fieldStatusMeta(view: FieldViewModel): { label: string; tone: string } {
    if (reviewedKeys.includes(view.key)) return { label: "확인함", tone: "reviewed" };
    if (view.field.confidence === "실패") return { label: "못 읽음", tone: "unread" };
    return { label: "미확인", tone: "unreviewed" };
  }

  function renderSourceDetails() {
    const shortByDomain = new Map<string, FieldViewModel[]>();
    const clauseFields: FieldViewModel[] = [];
    for (const view of fields) {
      if (CLAUSE_FIELDS.has(view.field.field_name)) {
        clauseFields.push(view);
        continue;
      }
      const domain = REVIEW_DOMAIN_BY_FIELD[view.field.field_name] ?? "etc";
      const bucket = shortByDomain.get(domain) ?? [];
      bucket.push(view);
      shortByDomain.set(domain, bucket);
    }
    return (
      <>
        <div className="review-domain-flow">
          {REVIEW_DOMAINS.filter((domain) => shortByDomain.has(domain.key)).map((domain) => (
            <Fragment key={domain.key}>
              <h3 className="review-domain-heading">{domain.title}</h3>
              {shortByDomain.get(domain.key)!.map((view) => {
                const meta = fieldStatusMeta(view);
                return (
                  <div className="review-field" key={view.key}>
                    <div className="review-field__head">
                      <strong>{fieldTitle(view)}</strong>
                      <span className={`review-status-chip review-status-chip--${meta.tone}`}>{meta.label}</span>
                    </div>
                    <span className="review-field__value">{displayViewValue(view, drafts)}</span>
                  </div>
                );
              })}
            </Fragment>
          ))}
        </div>
        {clauseFields.length > 0 && (
          <section className="review-clause-section">
            <h3>조항 원문</h3>
            {clauseFields.map((view) => {
              const items = clauseValues(view.field);
              const lines = items.length ? items : splitClauseText(displayViewValue(view, drafts));
              return (
                <details className="review-clause" key={view.key}>
                  <summary>{fieldTitle(view)}</summary>
                  <ul className="review-clause__list">
                    {lines.map((line, index) => <li key={index}>{line}</li>)}
                  </ul>
                </details>
              );
            })}
          </section>
        )}
      </>
    );
  }

  async function confirm() {
    setCorrectionError("");
    setConfirmationError("");
    setAnalysisError("");
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
      } catch {
        setCorrectionError(
          "수정한 내용을 저장하지 못했습니다. 입력한 내용은 이 화면에 남아 있습니다.",
        );
        setSubmitting(false);
        return;
      }
    }

    let inputSnapshotId = confirmedInputSnapshotId;
    if (!extractionConfirmed) {
      try {
        const snapshot = await mvpService.confirmExtraction(contractId);
        setExtractionConfirmed(true);
        setConfirmedInputSnapshotId(snapshot.input_snapshot_id);
        inputSnapshotId = snapshot.input_snapshot_id;
      } catch {
        setConfirmationError(
          "문서 내용 확인을 완료하지 못했습니다. 잠시 후 다시 시도해 주세요.",
        );
        setSubmitting(false);
        return;
      }
    }

    if (analysisStartUncertain && inputSnapshotId) {
      try {
        const runs = await mvpService.getAnalysisRuns(contractId);
        const recoveredRun = runs.find((run) => run.input_snapshot_id === inputSnapshotId);
        if (recoveredRun) {
          navigate(
            `/contracts/${contractId}/analyzing?analysisRunId=${encodeURIComponent(recoveredRun.analysis_run_id)}`,
          );
          return;
        }
        setAnalysisStartUncertain(false);
      } catch {
        setAnalysisError(
          "확인 결과 준비를 시작하지 못했습니다. 잠시 후 다시 시도해 주세요.",
        );
        setSubmitting(false);
        return;
      }
    }

    try {
      const run = await mvpService.startAnalysis(contractId);
      navigate(
        `/contracts/${contractId}/analyzing?analysisRunId=${encodeURIComponent(run.analysis_run_id)}`,
      );
    } catch {
      if (inputSnapshotId) {
        try {
          const runs = await mvpService.getAnalysisRuns(contractId);
          const recoveredRun = runs.find((run) => run.input_snapshot_id === inputSnapshotId);
          if (recoveredRun) {
            navigate(
              `/contracts/${contractId}/analyzing?analysisRunId=${encodeURIComponent(recoveredRun.analysis_run_id)}`,
            );
            return;
          }
        } catch {
          setAnalysisStartUncertain(true);
        }
      }
      setAnalysisError(
        "확인 결과 준비를 시작하지 못했습니다. 잠시 후 다시 시도해 주세요.",
      );
      setSubmitting(false);
    }
  }

  const reviewFinished = currentIndex >= queue.length;

  return (
    <PageShell
      layout="workspace"
      step="5 / 8"
      title="문서에서 읽은 내용 확인"
      description="중요한 내용부터 하나씩 원문과 비교해 주세요."
    >
      <div className="stack">
        {status === "loading" && (
          <LoadingState
            title="문서 읽기 상태를 확인하는 중"
            description="서버에서 문서 읽기 상태를 확인하고 있습니다."
          />
        )}
        {status === "processing" && (
          <LoadingState
            title={runStatus === "pending" ? "문서 읽기 대기 중" : "문서에서 값을 읽는 중"}
            description="완료될 때까지 실제 처리 상태를 확인하고 있습니다."
          />
        )}
        {status === "error" && (
          <ErrorState
            title="문서에서 읽은 내용을 불러오지 못했습니다"
            description={errorMessage}
            retryLabel="문서 다시 올리기"
            onRetry={() => navigate(`/contracts/${contractId}/upload`)}
          />
        )}
        {status === "success" && fields.length === 0 && (
          <EmptyState
            title="확인할 문서 내용이 없습니다"
            description="문서를 다시 업로드하거나 처리 상태를 확인해 주세요."
          />
        )}
        {status === "success" && fields.length > 0 && (
          <>
            <div className="guided-review-progress" role="status">
              <span>중요한 내용 {queue.length}개 중 {completedCount}개를 확인했습니다.</span>
              <div className="guided-review-progress__bar">
                <span style={{ width: `${queue.length ? (completedCount / queue.length) * 100 : 0}%` }} />
              </div>
            </div>

            {!reviewFinished && currentItem && (
              <section className="guided-review-step" aria-label="현재 확인할 내용">
                {currentIndex > 0 && (
                  <button
                    className="secondary guided-review-previous"
                    type="button"
                    disabled={submitting}
                    onClick={() => setCurrentIndex((index) => Math.max(0, index - 1))}
                  >
                    이전 내용 보기
                  </button>
                )}
                <GuidedReviewCard
                  item={currentItem}
                  draftValue={drafts[currentItem.key]}
                  busy={submitting}
                  onConfirm={() => markReviewed(currentItem)}
                  onChange={(value) => changeCurrent(currentItem, value)}
                  onCannotVerify={(reason) => markCannotVerify(currentItem, reason)}
                />
              </section>
            )}

            {reviewFinished && (
              <section className="guided-review-complete" aria-labelledby="review-complete-title">
                <p>내용 확인 완료</p>
                <h2 id="review-complete-title">중요한 내용을 모두 확인했습니다</h2>
                <div className="guided-review-complete__counts">
                  <span>확인한 항목 <strong>{reviewedItems.length}개</strong></span>
                  <span>확인하지 못한 항목 <strong>{unresolvedItems.length}개</strong></span>
                </div>
                <p>확인하지 못한 내용도 결과에서 물어볼 항목으로 안내합니다.</p>
                {unresolvedItems.length > 0 && (
                  <ul>
                    {unresolvedItems.map((item) => (
                      <li key={item.key}>
                        {item.title} · {reasonLabels[unresolvedReasonByKey[item.key]]}
                      </li>
                    ))}
                  </ul>
                )}
                {correctionError && <p className="error" role="alert">{correctionError}</p>}
                {confirmationError && <p className="error" role="alert">{confirmationError}</p>}
                {analysisError && <p className="error" role="alert">{analysisError}</p>}
                <div className="guided-review-complete__actions">
                  <button
                    className="secondary"
                    type="button"
                    disabled={submitting}
                    onClick={() => setCurrentIndex(Math.max(0, queue.length - 1))}
                  >
                    이전 내용 보기
                  </button>
                  <button type="button" disabled={submitting} onClick={() => void confirm()}>
                    {submitting ? "확인 결과를 준비하는 중…" : "이 내용으로 확인 결과 준비하기"}
                  </button>
                </div>
              </section>
            )}

            <details className="review-source-details">
              <summary>문서에서 읽은 전체 내용 보기</summary>
              <div className="review-source-details__body">
                {renderSourceDetails()}
              </div>
            </details>
          </>
        )}
      </div>
    </PageShell>
  );
}
