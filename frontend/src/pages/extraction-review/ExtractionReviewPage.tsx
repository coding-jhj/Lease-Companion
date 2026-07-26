import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { EmptyState, ErrorState, LoadingState } from "../../components/feedback/AsyncState";
import { PageShell } from "../../components/layout/PageShell";
import { GuidedReviewCard } from "../../features/extraction-review/GuidedReviewCard";
import {
  SituationAnswers,
  emptySituationAnswer,
  situationAnswerFromContract,
  situationAnswered,
  type SituationAnswer,
} from "../../features/extraction-review/SituationAnswers";
import {
  buildReviewPlan,
  type ReviewQueueItem,
  type ReviewSection,
} from "../../features/extraction-review/reviewQueue";
import {
  clauseValues,
  correctionValue,
  fieldViewModels,
  reviewStatusMeta,
} from "../../features/extraction-review/viewModel";
import { mvpService } from "../../services/mvpService";
import type {
  CorrectionRequestDto,
  DocumentExtractionDto,
  ExtractionConfirmationRequestDto,
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

const unresolvedIssueCodes: Record<
  CannotVerifyReason,
  "not_stated" | "unreadable" | "ambiguous"
> = {
  not_stated: "not_stated",
  unreadable: "unreadable",
  unknown_location: "ambiguous",
};

const REVIEW_SECTIONS: Array<{
  key: ReviewSection;
  title: string;
  description: string;
}> = [
  {
    key: "money_direct",
    title: "금전 피해로 이어질 수 있는 내용",
    description: "보증금·월세·계좌·등기 권리",
  },
  {
    key: "dispute_direct",
    title: "책임과 특약",
    description: "수리비·원상복구·관리비·계약 조건",
  },
  {
    key: "suspected_issue",
    title: "직접 알려주실 내용",
    description: "문서에 없거나 분명하지 않아 직접 답해야 하는 부분",
  },
  {
    key: "manual_or_unreadable",
    title: "못 읽은 내용",
    description: "글자가 흐리거나 문서에 없는 부분",
  },
  {
    key: "grouped",
    title: "나머지 내용",
    description: "위 네 가지에 없는 기본 정보",
  },
];

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
  const [verificationByKey, setVerificationByKey] = useState<Record<string, VerificationStatus>>({});
  const [reviewedKeys, setReviewedKeys] = useState<string[]>([]);
  const [savedDraftKeys, setSavedDraftKeys] = useState<string[]>([]);
  // 한 항목씩 넘기던 큐 대신 구역을 고르고 그 안 항목을 한 번에 본다.
  const [activeSection, setActiveSection] = useState<ReviewSection | null>(null);
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
  const queue = buildReviewPlan(fields);
  const reviewedKeySet = new Set(reviewedKeys);
  const sectionSummaries = REVIEW_SECTIONS.map((section) => {
    const items = queue.filter((item) => item.section === section.key);
    return {
      ...section,
      items,
      // 확인 불가로 표시한 항목도 처리를 마친 것으로 센다. 남은 개수가 줄지 않으면 다음 구역을 못 찾는다.
      completedCount: items.filter(
        (item) => reviewedKeys.includes(item.key) || unresolvedReasonByKey[item.key] !== undefined,
      ).length,
    };
  });
  // "직접 알려주실 내용"은 계약 상황 질문을 담고 있어 문서 항목이 없어도 항상 남긴다.
  const visibleSections = sectionSummaries.filter(
    (section) => section.items.length > 0 || section.key === "suspected_issue",
  );
  const currentSection = visibleSections.find((section) => section.key === activeSection)
    ?? visibleSections[0]
    ?? null;
  const currentSectionItems = currentSection ? currentSection.items : [];
  const completedCount = queue.filter((item) => reviewedKeys.includes(item.key)).length;
  const reviewedItems = queue.filter((item) => reviewedKeys.includes(item.key));
  const unresolvedItems = queue.filter((item) => unresolvedReasonByKey[item.key] !== undefined);
  const sectionHandledCount = currentSectionItems.filter(
    (item) => reviewedKeySet.has(item.key) || unresolvedReasonByKey[item.key] !== undefined,
  ).length;
  const allHandled = queue.length > 0 && queue.every(
    (item) => reviewedKeySet.has(item.key) || unresolvedReasonByKey[item.key] !== undefined,
  );
  const situationReady = situationAnswered(situation);
  // 묶음 확인은 "나머지 내용"에서만 쓴다. 돈·책임 항목까지 한 번에 넘기면 확인이 형식만 남는다.
  const bulkConfirmItems = currentSectionItems.filter((item) => (
    item.section === "grouped"
    && item.bulkConfirmAllowed
    && !reviewedKeySet.has(item.key)
    && unresolvedReasonByKey[item.key] === undefined
    && !Object.prototype.hasOwnProperty.call(drafts, item.key)
    && (verificationByKey[item.key] ?? item.view.field.verification_status) === "unverified"
  ));
  const currentSectionReady = sectionHandledCount === currentSectionItems.length
    && (currentSection?.key !== "suspected_issue" || situationReady);
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
      const loadedQueue = buildReviewPlan(loadedFields);
      const firstUnverifiedIndex = loadedQueue.findIndex(
        (item) => !loadedReviewedKeys.includes(item.key),
      );
      const loadedSituation = situationAnswerFromContract(contract);
      setDocuments(extractedDocuments);
      setSituation(loadedSituation);
      setDrafts({});
      setSavedDraftKeys([]);
      // 아직 확인하지 않은 항목이 있는 첫 구역부터 연다.
      setActiveSection(
        firstUnverifiedIndex === -1
          ? (situationAnswered(loadedSituation)
              ? loadedQueue[0]?.section ?? null
              : "suspected_issue")
          : loadedQueue[firstUnverifiedIndex].section,
      );
      setReviewFinished(
        firstUnverifiedIndex === -1
        && loadedQueue.length > 0
        && situationAnswered(loadedSituation),
      );
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

  function markGroupedItemsReviewed() {
    const keys = bulkConfirmItems.map((item) => item.key);
    if (keys.length === 0) return;

    setExtractionConfirmed(false);
    setAnalysisStartUncertain(false);
    setReviewedKeys((current) => [...new Set([...current, ...keys])]);
    setVerificationByKey((current) => {
      const next = { ...current };
      for (const key of keys) next[key] = "confirmed";
      return next;
    });
  }

  function selectSection(section: ReviewSection) {
    setReviewFinished(false);
    setActiveSection(section);
  }

  function advanceSection() {
    if (!currentSection || !currentSectionReady) return;

    const currentIndex = visibleSections.findIndex((section) => section.key === currentSection.key);
    const followingSection = visibleSections[currentIndex + 1];
    if (followingSection) {
      selectSection(followingSection.key);
      return;
    }

    const pendingSection = visibleSections.find((section) => (
      section.key !== currentSection.key
      && (section.completedCount < section.items.length
        || (section.key === "suspected_issue" && !situationReady))
    ));
    if (pendingSection) {
      selectSection(pendingSection.key);
      return;
    }

    if (allHandled && situationReady) setReviewFinished(true);
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
      title="읽은 내용 확인"
      description="계약서와 같은지 확인해 주세요."
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
            <nav className="review-section-nav" aria-label="확인 묶음">
              {sectionSummaries.map((section, index) => (
                // 번호는 구역 정의 순서를 그대로 쓴다. 빈 구역이 있어도 번호가 흔들리지 않는다.
                !visibleSections.includes(section) ? null : (
                  <button
                    className={`review-section-nav__item${
                      !reviewFinished && currentSection?.key === section.key ? " review-section-nav__item--active" : ""
                    }`}
                    type="button"
                    key={section.key}
                    aria-current={!reviewFinished && currentSection?.key === section.key ? "step" : undefined}
                    onClick={() => selectSection(section.key)}
                  >
                    <span className="review-section-nav__number">{index + 1}</span>
                    <strong>{section.title}</strong>
                    <span>
                      {section.completedCount} / {section.items.length}
                    </span>
                  </button>
                )
              ))}
            </nav>

            <div className="guided-review-progress">
              <div className="guided-review-progress__head">
                <span className="guided-review-progress__label">확인한 내용</span>
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
                aria-label={`중요한 내용 ${queue.length}개 중 ${completedCount}개 확인`}
              >
                <span style={{ width: `${queue.length ? (completedCount / queue.length) * 100 : 0}%` }} />
              </div>
            </div>

            {!reviewFinished && currentSection && (
              <section className="guided-review-step" aria-label="현재 확인할 내용">
                <header className="review-current-section">
                  <div>
                    <h2>{currentSection.title}</h2>
                    <p>{currentSection.description}</p>
                  </div>
                  <span className="review-current-section__count">
                    {`${currentSectionItems.length}개`}
                  </span>
                </header>
                {currentSection.key === "suspected_issue" && (
                  <>
                    <SituationAnswers
                      value={situation}
                      busy={submitting}
                      onChange={(next) => {
                        setSituation(next);
                        setExtractionConfirmed(false);
                      }}
                    />
                  </>
                )}
                <section className="grouped-review-panel" aria-labelledby="grouped-review-title">
                  <header className="grouped-review-panel__head">
                    <div>
                      <h3 id="grouped-review-title">{currentSection.title} 모아보기</h3>
                      <p>
                        전체 {currentSectionItems.length}개 · 확인 {sectionHandledCount}개 · 남은 항목{" "}
                        {currentSectionItems.length - sectionHandledCount}개
                      </p>
                    </div>
                    {currentSection.key === "grouped" && (
                      <button
                        type="button"
                        disabled={submitting || bulkConfirmItems.length === 0}
                        onClick={markGroupedItemsReviewed}
                      >
                        {bulkConfirmItems.length}개 모두 문서와 같아요
                      </button>
                    )}
                  </header>
                  {currentSection.key === "grouped" && (
                    <p className="grouped-review-panel__notice">
                      고쳤거나 따로 확인이 필요한 항목은 묶음 확인에서 빠집니다.
                    </p>
                  )}
                  <ul className="grouped-review-list">
                    {currentSectionItems.map((item) => {
                        const meta = fieldStatusMeta(item.view);
                        const reviewed = reviewedKeySet.has(item.key);
                        const unresolved = unresolvedReasonByKey[item.key] !== undefined;
                        return (
                          <li className="grouped-review-list__item" key={item.key}>
                            <div
                              className="grouped-review-list__summary"
                            >
                              <span className="grouped-review-list__title">
                                <strong>{item.title}</strong>
                                <span>{displayValue(item, drafts)}</span>
                              </span>
                              <span className="grouped-review-list__status">
                                <span className={`review-status-chip review-status-chip--${meta.tone}`}>
                                  {meta.label}
                                </span>
                              </span>
                            </div>
                            <div className="grouped-review-list__body">
                              {item.reasons.length > 0 && (
                                <div className="review-item-reasons">
                                  <ul aria-label="이 내용을 확인하는 이유">
                                    {item.reasons.map((reason) => <li key={reason}>{reason}</li>)}
                                  </ul>
                                </div>
                              )}
                              <GuidedReviewCard
                                item={item}
                                draftValue={drafts[item.key]}
                                busy={submitting}
                                completionLabel={reviewed ? "확인 완료" : unresolved ? "확인하지 못함" : undefined}
                                onConfirm={() => markReviewed(item)}
                                onChange={(value) => changeCurrent(item, value)}
                                onCannotVerify={(reason) => markCannotVerify(item, reason)}
                              />
                            </div>
                          </li>
                        );
                      })}
                  </ul>
                </section>
                <button
                  className="guided-review-step__finish"
                  type="button"
                  disabled={submitting || !currentSectionReady}
                  onClick={advanceSection}
                >
                  {(() => {
                    if (!currentSectionReady) {
                      return currentSection.key === "suspected_issue" && !situationReady
                        ? "계약 유형을 골라 주세요"
                        : `남은 ${currentSectionItems.length - sectionHandledCount}개를 확인해 주세요`;
                    }
                    const currentIndex = visibleSections.findIndex((section) => section.key === currentSection.key);
                    const followingSection = visibleSections[currentIndex + 1];
                    if (followingSection) return `다음 구역: ${followingSection.title}`;
                    const pendingSection = visibleSections.find((section) => (
                      section.key !== currentSection.key
                      && (section.completedCount < section.items.length
                        || (section.key === "suspected_issue" && !situationReady))
                    ));
                    return pendingSection
                      ? `남은 구역: ${pendingSection.title}`
                      : "전체 확인 내용 보기";
                  })()}
                </button>
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
                    onClick={() => setReviewFinished(false)}
                  >
                    이전 내용 보기
                  </button>
                  <button type="button" disabled={submitting} onClick={() => void confirm()}>
                    {submitting ? "확인 결과를 준비하는 중…" : "이 내용으로 확인 결과 준비하기"}
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
