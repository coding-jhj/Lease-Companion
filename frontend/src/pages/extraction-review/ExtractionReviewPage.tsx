import { useEffect, useRef, useState } from "react";
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
  const rawReviewedFields = fields.filter((view) => reviewedKeys.includes(view.key));
  const rawUnreadFields = fields.filter((view) => (
    !reviewedKeys.includes(view.key)
    && view.field.confidence === "실패"
  ));
  const rawUnreviewedFields = fields.filter((view) => (
    !reviewedKeys.includes(view.key)
    && view.field.confidence !== "실패"
  ));
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

  function renderSummaryGroup(title: string, items: FieldViewModel[]) {
    return (
      <section className="review-source-group">
        <h3>{title}</h3>
        {items.length === 0 ? (
          <p>해당 내용이 없습니다.</p>
        ) : (
          <ul>
            {items.map((view) => (
              <li key={view.key}>
                <strong>{queue.find((item) => item.key === view.key)?.title ?? view.label}</strong>
                <span>{displayViewValue(view, drafts)}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
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
            <p className="guided-review-progress" role="status">
              중요한 내용 {queue.length}개 중 {completedCount}개를 확인했습니다.
            </p>

            {!reviewFinished && currentItem && (
              <section className="guided-review-step" aria-label="현재 확인할 내용">
                <GuidedReviewCard
                  item={currentItem}
                  draftValue={drafts[currentItem.key]}
                  busy={submitting}
                  onConfirm={() => markReviewed(currentItem)}
                  onChange={(value) => changeCurrent(currentItem, value)}
                  onCannotVerify={(reason) => markCannotVerify(currentItem, reason)}
                />
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
                {renderSummaryGroup("확인한 내용", rawReviewedFields)}
                {renderSummaryGroup("아직 확인하지 않은 내용", rawUnreviewedFields)}
                {renderSummaryGroup("문서에서 읽지 못한 내용", rawUnreadFields)}
              </div>
            </details>
          </>
        )}
      </div>
    </PageShell>
  );
}
