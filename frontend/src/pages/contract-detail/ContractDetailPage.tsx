import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { Link, useNavigate, useParams } from "react-router-dom";
import { EmptyState, ErrorState, LoadingState } from "../../components/feedback/AsyncState";
import { PageShell } from "../../components/layout/PageShell";
import { normalizeAction } from "../../features/question-cards/actionNormalization";
import {
  POST_ACTION_PHASES,
  STANDARD_POST_ACTIONS,
  phaseForAction,
  standardPostActionFor,
  type StandardPostAction,
} from "../../features/post-contract-actions/phases";
import { plainGuideById, plainJudgmentGuides } from "../../features/judgment-results/plainGuides";
import { mvpService } from "../../services/mvpService";
import type {
  AnalysisRunSummaryDto,
  ChecklistItemKind,
  ChecklistItemStateDto,
  DocumentDto,
  GuidanceActionItemDto,
} from "../../types/api";
import { contractIdFromRoute } from "../../utils/contractId";

interface ChecklistViewItem extends GuidanceActionItemDto {
  kind: ChecklistItemKind;
  storageKind: ChecklistItemKind;
  resultIds: string[];
  done: boolean;
  updated_at: string | null;
  writable: boolean;
  standardGuide?: StandardPostAction;
}

const analysisStatusLabels: Record<AnalysisRunSummaryDto["status"], string> = {
  pending: "대기 중",
  running: "결과 준비 중",
  completed: "완료",
  failed: "실패",
};

// 처음에는 남은 항목 5개만 보여준다. 22개가 한 번에 쌓이면 화면이 4배로 길어진다.
const INITIAL_VISIBLE_ITEMS = 5;

export function ContractDetailPage() {
  const { contractId: routeContractId } = useParams();
  const contractId = contractIdFromRoute(routeContractId);
  const navigate = useNavigate();
  const [items, setItems] = useState<ChecklistViewItem[]>([]);
  // 규칙/판정 id → 연결된 판정 id(J). 체크리스트 항목의 쉬운 설명·금전 문제 가이드를 찾는 데 쓴다.
  const [judgmentByResultId, setJudgmentByResultId] = useState<Record<string, string | null>>({});
  const [analysisRuns, setAnalysisRuns] = useState<AnalysisRunSummaryDto[]>([]);
  const [documents, setDocuments] = useState<DocumentDto[]>([]);
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [errorMessage, setErrorMessage] = useState("");
  const [updateError, setUpdateError] = useState("");
  const [savingItemKey, setSavingItemKey] = useState("");
  const [expandedSections, setExpandedSections] = useState<string[]>([]);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState("");

  async function loadContractDetail() {
    setStatus("loading");
    setErrorMessage("");
    try {
      const [states, detail, runs, uploadedDocuments] = await Promise.all([
        mvpService.getChecklist(contractId),
        mvpService.getAnalysisDetail(contractId).catch(() => null),
        mvpService.getAnalysisRuns(contractId),
        mvpService.getDocuments(contractId),
      ]);
      const resultToJudgment: Record<string, string | null> = {};
      for (const rule of detail?.result?.results ?? []) resultToJudgment[rule.rule_id] = rule.judgment_id;
      for (const judgment of detail?.result?.judgments ?? []) resultToJudgment[judgment.judgment_id] = judgment.judgment_id;
      setJudgmentByResultId(resultToJudgment);
      const stateByKey = new Map(states.map((item) => [item.kind + ":" + item.item_key, item]));
      const rawGeneratedItems: Array<GuidanceActionItemDto & { kind: ChecklistItemKind; resultId: string }> =
        detail?.generation_result
          ? [...detail.generation_result.items, ...detail.generation_result.judgment_items].flatMap(
            (guidance) => [
              ...guidance.signing_checklist_items.map((item) => ({ ...item, kind: "checklist" as const, resultId: "rule_id" in guidance ? guidance.rule_id : guidance.judgment_id })),
              ...guidance.post_contract_action_items.map((item) => ({ ...item, kind: "post_action" as const, resultId: "rule_id" in guidance ? guidance.rule_id : guidance.judgment_id })),
            ],
          )
          : [];
      const generatedKeys = new Set(rawGeneratedItems.map((item) => item.kind + ":" + item.item_key));
      const compacted = new Map<string, ChecklistViewItem>();
      for (const item of rawGeneratedItems) {
        const normalized = normalizeAction(item.text, item.kind);
        const saved = stateByKey.get(item.kind + ":" + item.item_key);
        const compactKey = normalized.kind + ":" + normalized.identity;
        const previous = compacted.get(compactKey);
        if (previous) {
          previous.done ||= saved?.done ?? false;
          previous.resultIds = [...new Set([...previous.resultIds, item.resultId])];
          if (saved?.updated_at && (!previous.updated_at || saved.updated_at > previous.updated_at)) previous.updated_at = saved.updated_at;
          continue;
        }
        compacted.set(compactKey, {
          item_key: item.item_key,
          text: normalized.text,
          kind: normalized.kind,
          storageKind: item.kind,
          resultIds: [item.resultId],
          done: saved?.done ?? false,
          updated_at: saved?.updated_at ?? null,
          writable: true,
        });
      }
      // 생성 결과에 빠진 공식 계약 후 행동도 같은 저장 API를 쓰는 체크 항목으로
      // 보충한다. 생성 문구와 의미가 같은 항목은 기존 생성 item_key를 유지한다.
      const matchedStandardIds = new Set(
        [...compacted.values()]
          .filter((item) => item.kind === "post_action")
          .map((item) => standardPostActionFor(item.text)?.id)
          .filter((id): id is string => Boolean(id)),
      );
      if (detail?.generation_result) {
        for (const standard of STANDARD_POST_ACTIONS) {
          if (matchedStandardIds.has(standard.id)) continue;
          const saved = stateByKey.get(`post_action:${standard.itemKey}`);
          compacted.set(`post_action:official:${standard.id}`, {
            item_key: standard.itemKey,
            text: standard.text,
            kind: "post_action",
            storageKind: "post_action",
            resultIds: [],
            done: saved?.done ?? false,
            updated_at: saved?.updated_at ?? null,
            writable: true,
            standardGuide: standard,
          });
          generatedKeys.add(`post_action:${standard.itemKey}`);
        }
      }
      const merged = [...compacted.values()];
      const legacy = states
        .filter((item) => !generatedKeys.has(item.kind + ":" + item.item_key))
        .map((item) => ({
          kind: item.kind,
          storageKind: item.kind,
          resultIds: [],
          item_key: item.item_key,
          text: `이전 분석 항목 (${item.item_key})`,
          done: item.done,
          updated_at: item.updated_at,
          writable: false,
        }));
      setItems([...merged, ...legacy]);
      setAnalysisRuns(runs);
      setDocuments(uploadedDocuments);
      setStatus("success");
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "계약 상세를 불러오지 못했습니다.");
      setStatus("error");
    }
  }

  useEffect(() => { void loadContractDetail(); }, [contractId]);

  async function toggle(item: ChecklistViewItem) {
    setSavingItemKey(item.item_key);
    setUpdateError("");
    try {
      const updated: ChecklistItemStateDto = await mvpService.updateChecklistItem(
        contractId,
        item.storageKind,
        item.item_key,
        !item.done,
      );
      setItems((current) => current.map((candidate) =>
        candidate.storageKind === updated.kind && candidate.item_key === updated.item_key
          ? { ...candidate, done: updated.done, updated_at: updated.updated_at }
          : candidate,
      ));
    } catch (error) {
      setUpdateError(error instanceof Error ? error.message : "체크 상태를 저장하지 못했습니다.");
    } finally {
      setSavingItemKey("");
    }
  }

  async function deleteContract() {
    if (!window.confirm("이 계약과 저장된 확인 결과를 삭제할까요? 삭제한 데이터는 복구할 수 없습니다.")) return;
    setDeleting(true);
    setDeleteError("");
    try {
      await mvpService.deleteContract(contractId);
      navigate("/contracts", { replace: true });
    } catch (error) {
      setDeleteError(error instanceof Error ? error.message : "계약을 삭제하지 못했습니다.");
      setDeleting(false);
    }
  }

  const checklistItems = items.filter((item) => item.kind === "checklist");
  const generatedPostActions = items.filter((item) => item.kind === "post_action");
  const postActions = generatedPostActions.map((item) => {
    const standardGuide = item.standardGuide ?? standardPostActionFor(item.text) ?? undefined;
    return standardGuide ? { ...item, text: standardGuide.text, standardGuide } : item;
  });
  const pendingChecklistItems = checklistItems.filter((item) => !item.done);
  const completedChecklistItems = checklistItems.filter((item) => item.done);
  const pendingPostActions = postActions.filter((item) => !item.done);
  const completedPostActions = postActions.filter((item) => item.done);
  const printableChecklistItems = checklistItems.filter((item) => item.writable);
  const hasCompletedItems = completedChecklistItems.length > 0 || completedPostActions.length > 0;
  const latestCompletedAnalysis = analysisRuns.find((run) => run.status === "completed");

  function printChecklist() {
    const previousTitle = document.title;
    document.title = `서명전_체크리스트_계약_${contractId}`;
    window.print();
    document.title = previousTitle;
  }

  function guideForItem(item: ChecklistViewItem) {
    for (const id of item.resultIds) {
      // 규칙/판정 id로 바로 가이드가 있으면 사용, 없으면 연결된 판정(J)으로 매핑해 찾는다.
      if (id in plainJudgmentGuides) return plainGuideById(id);
      const judgmentId = judgmentByResultId[id] ?? null;
      if (judgmentId && judgmentId in plainJudgmentGuides) return plainGuideById(judgmentId);
    }
    return plainGuideById(null);
  }

  function renderActionItems({
    title,
    description,
    entries,
    actionLabel,
    completedActionLabel,
    emptyMessage,
    collapsible = false,
    hideWhenEmpty = false,
    total = entries.length,
    groupByPhase = false,
  }: {
    title: string;
    /** 제목 아래 안내 문구. 남은 항목을 보여주는 섹션에만 전달한다(완료 섹션에는 넣지 않는다). */
    description?: string;
    entries: ChecklistViewItem[];
    actionLabel: string;
    completedActionLabel: string;
    emptyMessage: string;
    collapsible?: boolean;
    hideWhenEmpty?: boolean;
    /** 진행률 분모. 제목 글자로 분기하면 제목을 바꿀 때 조용히 0%로 굳는다. */
    total?: number;
    /** 계약 후 행동만 시기 4개로 묶어 보여준다. */
    groupByPhase?: boolean;
  }) {
    // 항목이 없으면 빈 칸을 만들지 않는다. 화면 절반이 비어 보이던 원인이다.
    if (hideWhenEmpty && entries.length === 0) return null;

    const expanded = expandedSections.includes(title);
    const visibleEntries = collapsible || expanded ? entries : entries.slice(0, INITIAL_VISIBLE_ITEMS);
    const hiddenCount = entries.length - visibleEntries.length;
    const renderItems = (list: ChecklistViewItem[]) => (
      <ul className="checklist-section__items">
        {list.map((item) => {
            const label = item.done ? completedActionLabel : actionLabel;
            const saving = savingItemKey === item.item_key;
            const guide = guideForItem(item);
            return (
              <li className={`check-item check-item--row${item.done ? " check-item--complete" : ""}`} key={item.kind + ":" + item.item_key}>
                {item.writable
                  ? <button
                    aria-label={`${item.text} ${label}`}
                    aria-pressed={item.done}
                    className="check-item__check"
                    type="button"
                    disabled={saving}
                    onClick={() => void toggle(item)}
                  >
                    <span aria-hidden="true">{saving ? "…" : item.done ? "✓" : ""}</span>
                  </button>
                  : <span className="check-item__status" aria-label="변경 불가">✕</span>}
                <span className="check-item__text">{item.text}</span>
                {item.resultIds.length > 0 && (
                  <span className="check-item__source">근거 판정 {item.resultIds.join(" · ")}</span>
                )}
                <details className="check-item__guide">
                  <summary>{item.standardGuide ? "방법과 공식 근거" : "쉽게 보기"}</summary>
                  <div className="check-item__guide-body">
                    {item.standardGuide ? (
                      <>
                        <p>{item.standardGuide.method}</p>
                        <p className="check-item__sources">
                          {item.standardGuide.sources.map((source, index) => (
                            <span key={source.url}>
                              {index > 0 && " · "}
                              <a href={source.url} target="_blank" rel="noreferrer">{source.name}</a>
                            </span>
                          ))}
                        </p>
                      </>
                    ) : (
                      <>
                        <p>{guide.explanation}</p>
                        <p className="check-item__guide-money">
                          <strong>확인하지 않으면</strong> {guide.financialImpact}
                        </p>
                      </>
                    )}
                  </div>
                </details>
              </li>
            );
        })}
      </ul>
    );

    // 계약 후 행동은 시기 순으로 묶어 보여준다. 그 외 목록은 그대로 한 줄씩 둔다.
    const content = entries.length === 0
      ? <p className="checklist-section__empty">{emptyMessage}</p>
      : <>
        {groupByPhase
          ? POST_ACTION_PHASES.map((phase) => {
            const phaseItems = visibleEntries.filter((item) => phaseForAction(item.text) === phase);
            if (phaseItems.length === 0) return null;
            return (
              <section className="post-action-phase" key={phase}>
                <h3>{phase}</h3>
                {renderItems(phaseItems)}
              </section>
            );
          })
          : renderItems(visibleEntries)}
        {hiddenCount > 0 && (
          <button
            className="text-button checklist-section__more"
            type="button"
            onClick={() => setExpandedSections((current) => [...current, title])}
          >
            남은 항목 {hiddenCount}개 더 보기
          </button>
        )}
      </>;

    if (collapsible) {
      return (
        <section className="history-section checklist-section checklist-section--collapsible">
          <details className="completed-checklist-disclosure">
            <summary>
              <h2>{title}</h2>
              <span className="completed-checklist-disclosure__count">{entries.length}개</span>
              <span className="collapse-arrow" aria-hidden="true">▸</span>
            </summary>
            <div className="completed-checklist-disclosure__content">{content}</div>
          </details>
        </section>
      );
    }

    const done = total - entries.length;

    return (
      <section className="history-section checklist-section">
        <div className="checklist-section__head">
          <h2>{title}</h2>
          <span className="checklist-section__count">{done} / {total} 확인 완료</span>
        </div>
        {description && <p className="checklist-section__description">{description}</p>}
        {total > 0 && (
          <div className="checklist-progress" role="progressbar" aria-valuemin={0} aria-valuemax={total} aria-valuenow={done} aria-label={`${title} ${done} / ${total} 확인 완료`}>
            <div className="checklist-progress__fill" style={{ width: `${(done / total) * 100}%` }} />
          </div>
        )}
        {content}
      </section>
    );
  }

  return (
    <PageShell layout="workspace" step="7 / 7" title="체크리스트와 계약 후 행동" description="확인한 항목을 계약 건에 저장하고 다시 열어볼 수 있습니다.">
      <div className="stack">
        {status === "loading" && <LoadingState title="계약 상세를 불러오는 중" description="체크리스트와 저장 이력을 준비하고 있습니다." />}
        {status === "error" && <ErrorState title="계약 상세를 불러오지 못했습니다" description={errorMessage} onRetry={() => void loadContractDetail()} />}
        {status === "success" && items.length === 0 && <EmptyState title="아직 체크리스트 항목이 없습니다" description="확인 결과가 준비되면 확인 행동이 여기에 표시됩니다." />}
        {status === "success" && items.length > 0 && (
          <div className="checklist-flow">
            {printableChecklistItems.length > 0 && (
              <div className="checklist-export-toolbar">
                <p>현재 서명 전 체크리스트를 인쇄하거나 PDF 파일로 저장할 수 있습니다.</p>
                <button className="secondary" type="button" onClick={printChecklist}>체크리스트 PDF 저장</button>
              </div>
            )}
            {createPortal(<article className="checklist-print-sheet" aria-hidden="true">
              <header>
                <p>슬기로운 계약생활</p>
                <h1>서명 전 체크리스트</h1>
                <dl>
                  <div><dt>계약 건</dt><dd>#{contractId}</dd></div>
                  <div><dt>확인 결과 기준</dt><dd>{latestCompletedAnalysis ? new Date(latestCompletedAnalysis.created_at).toLocaleString("ko-KR") : "최신 완료 확인 결과"}</dd></div>
                  <div><dt>출력일</dt><dd>{new Date().toLocaleDateString("ko-KR")}</dd></div>
                </dl>
              </header>
              <ol>
                {printableChecklistItems.map((item) => (
                  <li key={`print:${item.kind}:${item.item_key}`}>
                    <span className="checklist-print-sheet__mark" aria-hidden="true">{item.done ? "✓" : "□"}</span>
                    <div>
                      <strong>{item.text}</strong>
                      <span>{item.done ? "확인 완료" : "미확인"}</span>
                      {item.resultIds.length > 0 && <small>근거 판정 {item.resultIds.join(" · ")}</small>}
                    </div>
                  </li>
                ))}
              </ol>
              <footer>이 체크리스트는 확인한 문서 내용을 바탕으로 확인할 항목을 정리한 자료이며, 계약의 안전성이나 적법성을 확정하지 않습니다.</footer>
            </article>, document.body)}
            <div className="checklist-active-grid">
              {renderActionItems({
                title: "서명 전 체크리스트",
                description: "서명하기 전, 금전 피해와 분쟁으로 이어질 수 있는 항목을 한 번 더 확인해 보세요.",
                entries: pendingChecklistItems,
                actionLabel: "확인",
                completedActionLabel: "확인 취소",
                emptyMessage: "모든 서명 전 체크리스트 항목을 확인했습니다.",
                total: checklistItems.length,
              })}
              {renderActionItems({
                title: "계약 후 해야 할 행동",
                description: "계약 후 보증금과 임차인의 권리를 보호하기 위해 필요한 조치를 확인해 보세요.",
                entries: pendingPostActions,
                actionLabel: "완료",
                completedActionLabel: "완료 취소",
                emptyMessage: "현재 남아 있는 계약 후 행동이 없습니다.",
                hideWhenEmpty: true,
                total: postActions.length,
                groupByPhase: true,
              })}
            </div>
            {hasCompletedItems && (
              <div className="checklist-completed-grid">
                {renderActionItems({
                  title: "완료된 체크리스트 항목",
                  entries: completedChecklistItems,
                  actionLabel: "확인",
                  completedActionLabel: "확인 취소",
                  emptyMessage: "완료된 체크리스트 항목이 없습니다.",
                  collapsible: true,
                })}
                {renderActionItems({
                  title: "완료된 계약 후 행동",
                  entries: completedPostActions,
                  actionLabel: "완료",
                  completedActionLabel: "완료 취소",
                  emptyMessage: "완료된 계약 후 행동이 없습니다.",
                  collapsible: true,
                })}
              </div>
            )}
          </div>
        )}
        {updateError && <p className="error" role="alert">{updateError}</p>}
        {status === "success" && (
          <details className="history-fold">
            <summary>지난 기록 보기 (확인 결과 {analysisRuns.length}건 · 문서 {documents.length}건)</summary>
            <div className="history-grid">
              <section className="history-section">
                <h2>확인 결과 이력</h2>
              {analysisRuns.length === 0
                ? <p>저장된 확인 결과가 없습니다.</p>
                : <ul>{analysisRuns.map((run) => (
                  <li key={run.analysis_run_id}>
                    {run.status === "completed"
                      ? <Link to={`/contracts/${contractId}/report?analysisRunId=${encodeURIComponent(run.analysis_run_id)}`}>{new Date(run.created_at).toLocaleString("ko-KR")} · 확인 결과 보기</Link>
                      : <span>{new Date(run.created_at).toLocaleString("ko-KR")} · {analysisStatusLabels[run.status]}</span>}
                  </li>
                ))}</ul>}
              </section>
              <section className="history-section">
                <h2>문서 이력</h2>
              {documents.length === 0
                ? <p>업로드된 문서가 없습니다.</p>
                : <ul>{documents.map((document) => <li key={document.id}>{document.doc_type} · {document.filename}</li>)}</ul>}
              </section>
            </div>
          </details>
        )}
        <div className="page-actions">
          <Link className="button-link secondary" to={`/contracts/${contractId}/report`}>확인 결과 다시 보기</Link>
          <Link className="button-link" to="/contracts">대시보드로 돌아가기</Link>
        </div>
        {deleteError && <p className="error" role="alert">{deleteError}</p>}
        <button className="danger-button" type="button" disabled={deleting} onClick={() => void deleteContract()}>
          {deleting ? "계약 삭제 중" : "계약 삭제"}
        </button>
      </div>
    </PageShell>
  );
}
