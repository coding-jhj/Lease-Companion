import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { EmptyState, ErrorState, LoadingState } from "../../components/feedback/AsyncState";
import { PageShell } from "../../components/layout/PageShell";
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
      const generatedItems: Array<GuidanceActionItemDto & { kind: ChecklistItemKind }> =
        detail?.generation_result
          ? [...detail.generation_result.items, ...detail.generation_result.judgment_items].flatMap(
            (guidance) => [
              ...guidance.signing_checklist_items.map((item) => ({ ...item, kind: "checklist" as const })),
              ...guidance.post_contract_action_items.map((item) => ({ ...item, kind: "post_action" as const })),
            ],
          )
          : [];
      const generatedKeys = new Set(generatedItems.map((item) => item.kind + ":" + item.item_key));
      const merged = generatedItems.map((item) => {
        const saved = stateByKey.get(item.kind + ":" + item.item_key);
        return { ...item, done: saved?.done ?? false, updated_at: saved?.updated_at ?? null, writable: true };
      });
      const legacy = states
        .filter((item) => !generatedKeys.has(item.kind + ":" + item.item_key))
        .map((item) => ({
          kind: item.kind,
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
        item.kind,
        item.item_key,
        !item.done,
      );
      setItems((current) => current.map((candidate) =>
        candidate.kind === updated.kind && candidate.item_key === updated.item_key
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

  function renderItems(title: string, entries: ChecklistViewItem[]) {
    if (entries.length === 0) return null;
    return (
      <section className="history-section">
        <h2>{title}</h2>
        {entries.map((item) => (
          <label className="check-item" key={item.kind + ":" + item.item_key}>
            <input
              type="checkbox"
              checked={item.done}
              disabled={!item.writable || savingItemKey === item.item_key}
              onChange={() => void toggle(item)}
            />
            <span>{item.text}</span>
          </label>
        ))}
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
          <div className="checklist-grid">
            {renderItems("서명 전 체크리스트", checklistItems)}
            {renderItems("계약 직후 행동", postActions)}
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
