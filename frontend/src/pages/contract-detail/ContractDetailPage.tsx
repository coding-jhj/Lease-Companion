import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { EmptyState, ErrorState, LoadingState } from "../../components/feedback/AsyncState";
import { PageShell } from "../../components/layout/PageShell";
import { normalizeAction } from "../../features/question-cards/actionNormalization";
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
}

const analysisStatusLabels: Record<AnalysisRunSummaryDto["status"], string> = {
  pending: "대기 중",
  running: "분석 중",
  completed: "완료",
  failed: "실패",
};

export function ContractDetailPage() {
  const { contractId: routeContractId } = useParams();
  const contractId = contractIdFromRoute(routeContractId);
  const navigate = useNavigate();
  const [items, setItems] = useState<ChecklistViewItem[]>([]);
  const [analysisRuns, setAnalysisRuns] = useState<AnalysisRunSummaryDto[]>([]);
  const [documents, setDocuments] = useState<DocumentDto[]>([]);
  const [status, setStatus] = useState<"loading" | "success" | "error">("loading");
  const [errorMessage, setErrorMessage] = useState("");
  const [updateError, setUpdateError] = useState("");
  const [savingItemKey, setSavingItemKey] = useState("");
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
    if (!window.confirm("이 계약과 저장된 분석 이력을 삭제할까요? 삭제한 데이터는 복구할 수 없습니다.")) return;
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
  const postActions = items.filter((item) => item.kind === "post_action");
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

  function renderActionItems({
    title,
    entries,
    actionLabel,
    completedActionLabel,
    emptyMessage,
    collapsible = false,
  }: {
    title: string;
    entries: ChecklistViewItem[];
    actionLabel: string;
    completedActionLabel: string;
    emptyMessage: string;
    collapsible?: boolean;
  }) {
    const content = entries.length === 0
      ? <p className="checklist-section__empty">{emptyMessage}</p>
      : <div className="checklist-section__items">
        {entries.map((item) => {
          const label = item.done ? completedActionLabel : actionLabel;
          const saving = savingItemKey === item.item_key;
          return (
            <div className={`check-item check-item--button${item.done ? " check-item--complete" : ""}`} key={item.kind + ":" + item.item_key}>
              <span className="check-item__text">
                {item.text}
                {item.resultIds.length > 0 && <small className="check-item__source">근거 판정 {item.resultIds.join(" · ")}</small>}
              </span>
              {item.writable
                ? <button
                  aria-label={`${item.text} ${label}`}
                  className="check-item__button"
                  type="button"
                  disabled={saving}
                  onClick={() => void toggle(item)}
                >
                  {saving ? "저장 중" : label}
                </button>
                : <span className="check-item__status">변경 불가</span>}
            </div>
          );
        })}
      </div>;

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

    return (
      <section className="history-section checklist-section">
        <h2>{title}</h2>
        {content}
      </section>
    );
  }

  return (
    <PageShell layout="workspace" step="8 / 8" title="체크리스트와 계약 직후 행동" description="확인한 항목을 계약 건에 저장하고 다시 열어볼 수 있습니다.">
      <div className="stack">
        {status === "loading" && <LoadingState title="계약 상세를 불러오는 중" description="체크리스트와 저장 이력을 준비하고 있습니다." />}
        {status === "error" && <ErrorState title="계약 상세를 불러오지 못했습니다" description={errorMessage} onRetry={() => void loadContractDetail()} />}
        {status === "success" && items.length === 0 && <EmptyState title="아직 체크리스트 항목이 없습니다" description="리포트가 생성되면 확인 행동이 여기에 표시됩니다." />}
        {status === "success" && items.length > 0 && (
          <div className="checklist-flow">
            {printableChecklistItems.length > 0 && (
              <div className="checklist-export-toolbar">
                <p>현재 서명 전 체크리스트를 인쇄하거나 PDF 파일로 저장할 수 있습니다.</p>
                <button className="secondary" type="button" onClick={printChecklist}>체크리스트 PDF 저장</button>
              </div>
            )}
            <article className="checklist-print-sheet" aria-hidden="true">
              <header>
                <p>슬기로운 계약생활</p>
                <h1>서명 전 체크리스트</h1>
                <dl>
                  <div><dt>계약 건</dt><dd>#{contractId}</dd></div>
                  <div><dt>분석 기준</dt><dd>{latestCompletedAnalysis ? new Date(latestCompletedAnalysis.created_at).toLocaleString("ko-KR") : "최신 완료 분석"}</dd></div>
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
              <footer>이 체크리스트는 문서 분석을 바탕으로 확인할 항목을 정리한 자료이며, 계약의 안전성이나 적법성을 확정하지 않습니다.</footer>
            </article>
            <div className="checklist-active-grid">
              {renderActionItems({
                title: "서명 전 체크리스트",
                entries: pendingChecklistItems,
                actionLabel: "확인",
                completedActionLabel: "확인 취소",
                emptyMessage: "모든 서명 전 체크리스트 항목을 확인했습니다.",
              })}
              {renderActionItems({
                title: "계약 직후 행동",
                entries: pendingPostActions,
                actionLabel: "완료",
                completedActionLabel: "완료 취소",
                emptyMessage: "현재 남아 있는 계약 직후 행동이 없습니다.",
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
                  title: "완료된 계약 직후 행동",
                  entries: completedPostActions,
                  actionLabel: "완료",
                  completedActionLabel: "완료 취소",
                  emptyMessage: "완료된 계약 직후 행동이 없습니다.",
                  collapsible: true,
                })}
              </div>
            )}
          </div>
        )}
        {updateError && <p className="error" role="alert">{updateError}</p>}
        {status === "success" && (
          <div className="history-grid">
            <section className="history-section">
              <h2>분석 이력</h2>
              {analysisRuns.length === 0
                ? <p>저장된 분석 이력이 없습니다.</p>
                : <ul>{analysisRuns.map((run) => (
                  <li key={run.analysis_run_id}>
                    {run.status === "completed"
                      ? <Link to={`/contracts/${contractId}/report?analysisRunId=${encodeURIComponent(run.analysis_run_id)}`}>{new Date(run.created_at).toLocaleString("ko-KR")} · 완료 리포트 보기</Link>
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
        )}
        <div className="page-actions">
          <Link className="button-link secondary" to={`/contracts/${contractId}/report`}>리포트 다시 보기</Link>
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
