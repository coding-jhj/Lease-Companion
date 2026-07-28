import { useEffect, useRef, useState, type CSSProperties } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { EmptyState, ErrorState, LoadingState } from "../../components/feedback/AsyncState";
import { PageShell } from "../../components/layout/PageShell";
import { GuidedReviewCard } from "../../features/extraction-review/GuidedReviewCard";
import {
  emptySituationAnswer,
  situationAnswerFromContract,
  situationAnswered,
  type SituationAnswer,
} from "../../features/extraction-review/SituationAnswers";
import {
  buildReviewPlan,
  type ReviewQueueItem,
} from "../../features/extraction-review/reviewQueue";
import {
  clauseValues,
  correctionValue,
  fieldViewModels,
  requiresExternalConfirmation,
  reviewStatusMeta,
} from "../../features/extraction-review/viewModel";
import { mvpService } from "../../services/mvpService";
import type {
  CorrectionRequestDto,
  ContractType,
  DocumentExtractionDto,
  ExtractionConfirmationRequestDto,
  FieldViewModel,
  SchemaVersion,
  VerificationStatus,
} from "../../types/api";
import { contractIdFromRoute } from "../../utils/contractId";
import { PollTimeoutError, pollUntilTerminal } from "../../utils/pollUntilTerminal";

type DraftValue = string | string[];
type CannotVerifyReason =
  | "not_stated"
  | "unreadable"
  | "unknown_location"
  | "parse_failed"
  | "external_confirmation";

const reasonLabels: Record<CannotVerifyReason, string> = {
  not_stated: "문서에 적혀 있지 않음",
  unreadable: "문서에서 글자를 읽지 못함",
  unknown_location: "확인할 위치를 찾기 어려움",
  parse_failed: "내용 형태를 알아보지 못함",
  external_confirmation: "다른 자료에서 직접 확인 필요",
};

const unresolvedIssueCodes: Record<
  CannotVerifyReason,
  "not_stated" | "unreadable" | "ambiguous"
> = {
  not_stated: "not_stated",
  unreadable: "unreadable",
  unknown_location: "ambiguous",
  parse_failed: "ambiguous",
  external_confirmation: "ambiguous",
};

const UNREAD_SECTION = {
  key: "manual_or_unreadable" as const,
  title: "못 읽은 내용",
  description: "원본 계약서를 보면서 빈 내용을 채워 주세요.",
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

function sourceUnresolvedReason(item: ReviewQueueItem): CannotVerifyReason {
  if (requiresExternalConfirmation(item.view)) return "external_confirmation";
  switch (item.view.field.issue_code) {
    case "not_stated":
      return "not_stated";
    case "unreadable":
      return "unreadable";
    case "parse_failed":
      return "parse_failed";
    default:
      return "unknown_location";
  }
}

// 특약처럼 원문이 긴 항목은 카드 한 칸에 담으면 그 줄만 길어져 읽기 어렵다.
// 이런 항목은 나누지 않고 한 줄을 통째로 쓴다.
const WIDE_ITEM_TEXT_LENGTH = 100;

// 조항 원문 항목은 값 길이와 상관없이 항상 한 줄을 쓴다. 정규화 값이 짧게 들어와도
// 카드를 열면 조항이 여러 개로 펼쳐지기 때문에 값으로만 판단하면 놓친다.
const WIDE_FIELD_NAMES = new Set([
  "special_clauses",
  "main_clauses",
  "deposit_return_clause",
  "repair_responsibility_clause",
]);

function isWideItem(item: ReviewQueueItem, drafts: Record<string, DraftValue>): boolean {
  if (item.view.editor === "clause-list") return true;
  if (WIDE_FIELD_NAMES.has(item.fieldName)) return true;
  const draft = drafts[item.key];
  if (Array.isArray(draft)) return draft.length > 1;
  return displayValue(item, drafts).length >= WIDE_ITEM_TEXT_LENGTH;
}

// 긴 항목을 뺀 나머지 개수로 열 수를 정한다. 3의 배수면 3열(6개는 2줄로 고르게 나뉜다),
// 그 외 짝수면 2열, 홀수면 3열.
function reviewColumnCount(regularItemCount: number): number {
  if (regularItemCount <= 1) return 1;
  if (regularItemCount % 3 === 0) return 3;
  return regularItemCount % 2 === 0 ? 2 : 3;
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
  const [reviewFinished, setReviewFinished] = useState(false);
  const [situation, setSituation] = useState<SituationAnswer>(emptySituationAnswer);
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
  const queue = buildReviewPlan(fields).filter(
    (item) => item.section === UNREAD_SECTION.key,
  );
  const reviewedKeySet = new Set(reviewedKeys);
  const completedCount = queue.filter((item) => reviewedKeys.includes(item.key)).length;
  const reviewedItems = queue.filter((item) => reviewedKeys.includes(item.key));
  const unresolvedItems = queue.filter((item) => unresolvedReasonByKey[item.key] !== undefined);
  const sectionHandledCount = queue.filter(
    (item) => reviewedKeySet.has(item.key) || unresolvedReasonByKey[item.key] !== undefined,
  ).length;
  const allHandled = queue.every(
    (item) => reviewedKeySet.has(item.key) || unresolvedReasonByKey[item.key] !== undefined,
  );
  const situationReady = situationAnswered(situation);
  // 원문이 긴 항목은 한 줄을 통째로 쓰고, 남은 항목 수로 열 수를 정한다.
  const wideItemKeys = new Set(
    queue.filter((item) => isWideItem(item, drafts)).map((item) => item.key),
  );
  const sectionColumnCount = reviewColumnCount(queue.length - wideItemKeys.size);
  // 한 줄짜리 항목이 중간에 끼면 그 앞뒤 줄에 빈칸이 생긴다. 순서를 유지한 채 뒤로 모은다.
  const orderedSectionItems = [
    ...queue.filter((item) => !wideItemKeys.has(item.key)),
    ...queue.filter((item) => wideItemKeys.has(item.key)),
  ];
  const currentSectionReady = allHandled;
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
      const contract = await mvpService.getContract(contractId);
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
      const loadedSituation = situationAnswerFromContract(contract);
      setDocuments(extractedDocuments);
      setSituation(loadedSituation);
      setDrafts({});
      setSavedDraftKeys([]);
      setReviewFinished(false);
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
  }

  function markCannotVerify(item: ReviewQueueItem, reason: CannotVerifyReason) {
    setReviewedKeys((current) => current.filter((key) => key !== item.key));
    setUnresolvedReasonByKey((current) => ({ ...current, [item.key]: reason }));
  }

  function markAllUnreadReviewed() {
    const pendingItems = queue.filter(
      (item) => !reviewedKeySet.has(item.key) && unresolvedReasonByKey[item.key] === undefined,
    );
    if (pendingItems.length === 0) return;

    setExtractionConfirmed(false);
    setAnalysisStartUncertain(false);
    setUnresolvedReasonByKey((current) => {
      const next = { ...current };
      for (const item of pendingItems) next[item.key] = sourceUnresolvedReason(item);
      return next;
    });
    setReviewFinished(true);
  }

  function advanceSection() {
    if (!currentSectionReady) return;
    setReviewFinished(true);
  }

  function fieldStatusMeta(view: FieldViewModel): { label: string; tone: string } {
    return reviewStatusMeta(view, {
      reviewed: reviewedKeys.includes(view.key),
      unresolved: unresolvedReasonByKey[view.key] !== undefined,
    });
  }

  async function confirm() {
    setCorrectionError("");
    setConfirmationError("");
    setAnalysisError("");
    setSubmitting(true);

    // 계약 상황은 문서에서 읽을 수 없는 값이라 확인 완료 시점에 함께 저장한다.
    if (situation.contractType !== null) {
      try {
        await mvpService.saveSituation(contractId, {
          contract_type: situation.contractType,
          contract_stage: situation.contractStage,
          deposit_paid: situation.depositPaid,
          signed: situation.signed,
          move_in_date: situation.moveInDate || null,
          balance_payment_date: situation.balancePaymentDate || null,
          is_proxy_contract: situation.proxyStatus === "unknown"
            ? null
            : situation.proxyStatus === "yes",
        });
      } catch {
        setConfirmationError(
          "계약 상황을 저장하지 못했습니다. 잠시 후 다시 시도해 주세요.",
        );
        setSubmitting(false);
        return;
      }
    }

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
      const confirmationRequest: ExtractionConfirmationRequestDto = {
        schema_version: schemaVersion,
        contract_id: contractId,
        unresolved_fields: unresolvedItems.map((item) => ({
          document_type: item.view.document_type,
          field_name: item.fieldName,
          issue_code: unresolvedIssueCodes[unresolvedReasonByKey[item.key]],
        })),
      };
      try {
        const snapshot = await mvpService.confirmExtraction(contractId, confirmationRequest);
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

  return (
    <PageShell
      layout="workspace"
      step="4 / 7"
      title="못 읽은 내용 확인"
      description="문서에서 읽지 못한 항목을 원본 계약서와 비교해 입력해 주세요."
    >
      <div className="stack extraction-review-workspace">
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
            <div className="guided-review-progress">
              <div className="guided-review-progress__head">
                <span className="guided-review-progress__label">확인한 못 읽은 내용</span>
                <span className="guided-review-progress__count" role="status">
                  {completedCount}<em>{` / ${queue.length}`}</em>
                </span>
              </div>
              <div
                className="guided-review-progress__bar"
                role="progressbar"
                aria-valuemin={0}
                aria-valuemax={queue.length}
                aria-valuenow={completedCount}
                aria-label={`못 읽은 내용 ${queue.length}개 중 ${completedCount}개 확인`}
              >
                <span style={{ width: `${queue.length ? (completedCount / queue.length) * 100 : 0}%` }} />
              </div>
            </div>

            {!reviewFinished && (
              <section className="guided-review-step" aria-label="현재 확인할 내용">
                <header className="review-current-section">
                  <div>
                    <h2>{UNREAD_SECTION.title}</h2>
                    <p>{UNREAD_SECTION.description}</p>
                  </div>
                  <span className="review-current-section__count">
                    {`${queue.length}개`}
                  </span>
                </header>
                <section className="grouped-review-panel" aria-labelledby="grouped-review-title">
                  <header className="grouped-review-panel__head">
                    <div>
                      <h3 id="grouped-review-title">못 읽은 내용 모아보기</h3>
                      <p>
                        전체 {queue.length}개 · 확인 {sectionHandledCount}개 · 남은 항목{" "}
                        {queue.length - sectionHandledCount}개
                      </p>
                    </div>
                    {sectionHandledCount < queue.length && (
                      <button
                        type="button"
                        disabled={submitting}
                        onClick={markAllUnreadReviewed}
                      >
                        모두 확인하기
                      </button>
                    )}
                  </header>
                  {queue.length === 0 ? (
                    <div className="grouped-review-panel__empty">
                      문서에서 못 읽은 내용이 없습니다.
                    </div>
                  ) : (
                    <ul
                      className="grouped-review-list"
                      style={{ "--review-columns": sectionColumnCount } as CSSProperties}
                    >
                      {orderedSectionItems.map((item) => {
                        const meta = fieldStatusMeta(item.view);
                        const reviewed = reviewedKeySet.has(item.key);
                        const unresolved = unresolvedReasonByKey[item.key] !== undefined;
                        const wide = wideItemKeys.has(item.key);
                        return (
                          <li
                            className={`grouped-review-list__item${wide ? " grouped-review-list__item--wide" : ""}`}
                            key={item.key}
                          >
                            <div
                              className="grouped-review-list__summary"
                            >
                              <span className="grouped-review-list__title">
                                <strong>{item.title}</strong>
                              </span>
                              <span className="grouped-review-list__status">
                                <span className={`review-status-chip review-status-chip--${meta.tone}`}>
                                  {meta.label}
                                </span>
                              </span>
                            </div>
                            <div className="grouped-review-list__body">
                              <GuidedReviewCard
                                item={item}
                                draftValue={drafts[item.key]}
                                busy={submitting}
                                compactUnread
                                completionLabel={reviewed ? "확인 완료" : unresolved ? "확인하지 못함" : undefined}
                                onChange={(value) => changeCurrent(item, value)}
                                onCannotVerify={(reason) => markCannotVerify(item, reason)}
                              />
                            </div>
                          </li>
                        );
                      })}
                    </ul>
                  )}
                </section>
                <button
                  className="guided-review-step__finish"
                  type="button"
                  disabled={submitting || !currentSectionReady}
                  onClick={advanceSection}
                >
                  {currentSectionReady
                    ? "확인 완료"
                    : `남은 ${queue.length - sectionHandledCount}개를 입력해 주세요`}
                </button>
              </section>
            )}

            {reviewFinished && (
              <section className="guided-review-complete" aria-labelledby="review-complete-title">
                <p>못 읽은 내용 확인 완료</p>
                <h2 id="review-complete-title">분석 준비를 마쳐 주세요</h2>
                <div className="guided-review-complete__counts">
                  <span>확인한 항목 <strong>{reviewedItems.length}개</strong></span>
                  <span>확인하지 못한 항목 <strong>{unresolvedItems.length}개</strong></span>
                </div>
                {unresolvedItems.length > 0 && (
                  <ul>
                    {unresolvedItems.map((item) => (
                      <li key={item.key}>
                        {item.title} · {reasonLabels[unresolvedReasonByKey[item.key]]}
                      </li>
                    ))}
                  </ul>
                )}
                {!situationReady && (
                  <fieldset className="contract-type-inline" disabled={submitting}>
                    <legend>계약 유형만 선택해 주세요</legend>
                    <div>
                      {(["전세", "보증부 월세", "일반 월세"] as ContractType[]).map((type) => (
                        <label key={type}>
                          <input
                            type="radio"
                            name="review-contract-type"
                            value={type}
                            checked={situation.contractType === type}
                            onChange={() => {
                              setSituation((current) => ({ ...current, contractType: type }));
                              setExtractionConfirmed(false);
                            }}
                          />
                          {type}
                        </label>
                      ))}
                    </div>
                  </fieldset>
                )}
                {correctionError && <p className="error" role="alert">{correctionError}</p>}
                {confirmationError && <p className="error" role="alert">{confirmationError}</p>}
                {analysisError && <p className="error" role="alert">{analysisError}</p>}
                <div className="guided-review-complete__actions">
                  <button
                    className="secondary"
                    type="button"
                    disabled={submitting}
                    onClick={() => setReviewFinished(false)}
                  >
                    이전 내용 보기
                  </button>
                  <button
                    type="button"
                    disabled={submitting || !situationReady}
                    onClick={() => void confirm()}
                  >
                    {submitting
                      ? "확인 결과를 준비하는 중…"
                      : situationReady
                        ? "이 내용으로 확인 결과 준비하기"
                        : "계약 상황을 입력해 주세요"}
                  </button>
                </div>
              </section>
            )}

          </>
        )}
      </div>
    </PageShell>
  );
}
