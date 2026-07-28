import { useEffect, useRef, useState } from "react";
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

function externalSourceLabel(fieldName: string): string {
  const labels: Record<string, string> = {
    violation_building: "건축물대장",
    estimated_housing_value: "시세 자료",
    guarantee_eligibility_confirmed: "HUG 기준",
    lessor_sublease_authority_confirmed: "권한 자료",
    senior_claim_amount: "임대인 확인",
  };
  return labels[fieldName] ?? "확인 자료";
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
  const [expandedReviewKey, setExpandedReviewKey] = useState<string | null | undefined>(undefined);
  const [expandedReviewGroups, setExpandedReviewGroups] = useState<string[]>([]);
  const activePoll = useRef<AbortController | null>(null);

  const fields = fieldViewModels(documents);
  const queue = buildReviewPlan(fields).filter(
    (item) => item.section === UNREAD_SECTION.key,
  );
  const reviewedKeySet = new Set(reviewedKeys);
  const reviewedItems = queue.filter((item) => reviewedKeys.includes(item.key));
  const unresolvedItems = queue.filter((item) => unresolvedReasonByKey[item.key] !== undefined);
  const sectionHandledCount = queue.filter(
    (item) => reviewedKeySet.has(item.key) || unresolvedReasonByKey[item.key] !== undefined,
  ).length;
  const allHandled = queue.every(
    (item) => reviewedKeySet.has(item.key) || unresolvedReasonByKey[item.key] !== undefined,
  );
  const completedCount = sectionHandledCount;
  const pendingItems = queue.filter(
    (item) => !reviewedKeySet.has(item.key) && unresolvedReasonByKey[item.key] === undefined,
  );
  const unreadItems = pendingItems.filter((item) => !requiresExternalConfirmation(item.view));
  const externalItems = pendingItems.filter((item) => requiresExternalConfirmation(item.view));
  const handledItems = queue.filter(
    (item) => reviewedKeySet.has(item.key) || unresolvedReasonByKey[item.key] !== undefined,
  );
  const situationReady = situationAnswered(situation);
  const currentSectionReady = allHandled;
  const pendingCorrectionKeys = Object.keys(drafts).filter(
    (key) => !savedDraftKeys.includes(key),
  );
  const schemaVersion: SchemaVersion = documents.find(
    (document) => document.document_type === "contract",
  )?.schema_version ?? documents[0]?.schema_version ?? "1.8.0";
  const initiallyExpandedKey = unreadItems[0]?.key ?? externalItems[0]?.key;
  const activeExpandedKey = expandedReviewKey === undefined ? initiallyExpandedKey : expandedReviewKey;

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
      setExpandedReviewKey(undefined);
      setExpandedReviewGroups([]);
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

  function confirmCurrent(item: ReviewQueueItem) {
    setExtractionConfirmed(false);
    setAnalysisStartUncertain(false);
    setReviewedKeys((current) => [...new Set([...current, item.key])]);
    setVerificationByKey((current) => ({ ...current, [item.key]: "confirmed" }));
    setUnresolvedReasonByKey((current) => {
      const next = { ...current };
      delete next[item.key];
      return next;
    });
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
      title="확인할 항목"
      description="문서에서 확인하지 못한 내용을 입력하거나 다른 자료에서 확인해 주세요."
      eyebrow=""
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
            <div className="review-overall-progress">
              <span className="review-overall-progress__count" role="status">
                완료 {completedCount}<em>{` / ${queue.length}`}</em>
              </span>
              <div
                className="review-overall-progress__bar"
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
                <section className="review-accordion" aria-label="확인할 항목 목록">
                  {queue.length === 0 ? (
                    <div className="grouped-review-panel__empty">
                      문서에서 못 읽은 내용이 없습니다.
                    </div>
                  ) : (
                    <div className="compact-review-groups">
                      {([
                        { title: "직접 입력", items: unreadItems, action: "입력하기" },
                        { title: "다른 자료 확인", items: externalItems, action: "확인 방법" },
                      ] as const).map((group) => {
                        if (group.items.length === 0) return null;
                        const groupExpanded = expandedReviewGroups.includes(group.title);
                        const visibleItems = groupExpanded ? group.items : group.items.slice(0, 3);
                        const hiddenCount = group.items.length - visibleItems.length;
                        return (
                        <section className="compact-review-group" aria-labelledby={`compact-${group.action}-title`} key={group.title}>
                          <div className="compact-review-group__head">
                            <h3 id={`compact-${group.action}-title`}>{group.title}</h3>
                            <span>{group.items.length}개</span>
                          </div>
                          <ul className="compact-review-list">
                            {visibleItems.map((item) => {
                              const expanded = activeExpandedKey === item.key;
                              return (
                                <li className={`compact-review-item${expanded ? " compact-review-item--expanded" : ""}`} key={item.key}>
                                  <button
                                    type="button"
                                    className="compact-review-item__row"
                                    aria-expanded={expanded}
                                    aria-controls={`review-detail-${item.key}`}
                                    onClick={() => setExpandedReviewKey(expanded ? null : item.key)}
                                  >
                                    <strong>{item.title}</strong>
                                    <span className={`compact-review-item__badge${group.title === "직접 입력" ? " compact-review-item__badge--manual" : ""}`}>
                                      {group.title === "직접 입력" ? "입력 필요" : externalSourceLabel(item.fieldName)}
                                    </span>
                                    <span className="compact-review-item__action">
                                      <em>{group.action}</em>
                                      <span
                                        className={`compact-review-item__chevron${expanded ? " compact-review-item__chevron--open" : ""}`}
                                        aria-hidden="true"
                                      />
                                    </span>
                                  </button>
                                  {expanded && (
                                    <div className="compact-review-item__detail" id={`review-detail-${item.key}`}>
                                      <GuidedReviewCard
                                        item={item}
                                        draftValue={drafts[item.key]}
                                        busy={submitting}
                                        compactUnread
                                        inlineCompact
                                        onChange={(value) => {
                                          changeCurrent(item, value);
                                          setExpandedReviewKey(null);
                                        }}
                                        onConfirm={() => {
                                          confirmCurrent(item);
                                          setExpandedReviewKey(null);
                                        }}
                                        onCannotVerify={(reason) => {
                                          markCannotVerify(item, reason);
                                          setExpandedReviewKey(null);
                                        }}
                                      />
                                    </div>
                                  )}
                                </li>
                              );
                            })}
                          </ul>
                          {group.items.length > 3 && (
                            <button
                              className="compact-review-group__more"
                              type="button"
                              onClick={() => setExpandedReviewGroups((current) => groupExpanded
                                ? current.filter((title) => title !== group.title)
                                : [...current, group.title])}
                            >
                              {groupExpanded ? "접기" : `나머지 ${hiddenCount}개 보기`} <span aria-hidden="true">⌄</span>
                            </button>
                          )}
                        </section>
                        );
                      })}

                      {handledItems.length > 0 && (
                        <details className="compact-review-completed">
                          <summary>
                            <span>직접 확인했습니다</span>
                            <strong>{handledItems.length}개</strong>
                          </summary>
                          <ul>
                            {handledItems.map((item) => {
                              const meta = fieldStatusMeta(item.view);
                              return (
                                <li key={item.key}>
                                  <span>{item.title}</span>
                                  <strong>{meta.label}</strong>
                                </li>
                              );
                            })}
                          </ul>
                        </details>
                      )}

                      {pendingItems.length > 0 && (
                        <button
                          className="compact-review-start"
                          type="button"
                          onClick={() => setExpandedReviewKey(pendingItems[0].key)}
                        >
                          확인 시작하기
                        </button>
                      )}
                    </div>
                  )}
                </section>
                {currentSectionReady && (
                  <button
                    className="guided-review-step__finish"
                    type="button"
                    disabled={submitting}
                    onClick={advanceSection}
                  >
                    확인 완료
                  </button>
                )}
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
