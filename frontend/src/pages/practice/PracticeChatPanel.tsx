import { useEffect, useRef, useState } from "react";
import { practiceService } from "../../services/practiceService";
import type { PracticeConversationTurnDto } from "../../types/api";

interface PracticeChatPanelProps {
  sessionId: string;
  currentTurn: { turn_id: string; prompt: string } | null;
  latestTurn: PracticeConversationTurnDto | null;
  refreshToken: number;
  onClose?: () => void;
}

export function PracticeChatPanel({
  sessionId,
  currentTurn,
  latestTurn,
  refreshToken,
  onClose,
}: PracticeChatPanelProps) {
  const viewportRef = useRef<HTMLDivElement>(null);
  const stayAtBottomRef = useRef(true);
  const loadingOlderRef = useRef(false);
  const [items, setItems] = useState<PracticeConversationTurnDto[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const [showLatest, setShowLatest] = useState(false);
  const [error, setError] = useState("");

  function scrollToBottom(behavior: ScrollBehavior = "auto") {
    const viewport = viewportRef.current;
    if (!viewport) return;
    if (typeof viewport.scrollTo === "function") {
      viewport.scrollTo({ top: viewport.scrollHeight, behavior });
    } else {
      viewport.scrollTop = viewport.scrollHeight;
    }
    stayAtBottomRef.current = true;
    setShowLatest(false);
  }

  useEffect(() => {
    let active = true;
    setError("");
    if (latestTurn) {
      setItems((current) => (
        current.some((item) => item.practice_turn_id === latestTurn.practice_turn_id)
          ? current
          : [...current, latestTurn]
      ));
    }
    void practiceService.getMessages(sessionId).then((page) => {
      if (!active) return;
      setItems(
        latestTurn && !page.items.some((item) => item.practice_turn_id === latestTurn.practice_turn_id)
          ? [...page.items, latestTurn]
          : page.items,
      );
      setNextCursor(page.next_cursor);
      setHasMore(page.has_more);
      requestAnimationFrame(() => scrollToBottom());
    }).catch((reason: unknown) => {
      if (active) setError(reason instanceof Error ? reason.message : "대화 기록을 불러오지 못했습니다.");
    });
    return () => {
      active = false;
    };
  }, [sessionId, refreshToken, latestTurn]);

  useEffect(() => {
    if (stayAtBottomRef.current) requestAnimationFrame(() => scrollToBottom("smooth"));
  }, [currentTurn?.turn_id, currentTurn?.prompt, items.length]);

  async function loadOlder() {
    const viewport = viewportRef.current;
    if (!viewport || !hasMore || !nextCursor || loadingOlderRef.current) return;
    loadingOlderRef.current = true;
    setLoadingOlder(true);
    setError("");
    const previousHeight = viewport.scrollHeight;
    const previousTop = viewport.scrollTop;
    try {
      const page = await practiceService.getMessages(sessionId, nextCursor);
      setItems((current) => [...page.items, ...current]);
      setNextCursor(page.next_cursor);
      setHasMore(page.has_more);
      requestAnimationFrame(() => {
        const currentViewport = viewportRef.current;
        if (currentViewport) {
          currentViewport.scrollTop = currentViewport.scrollHeight - previousHeight + previousTop;
        }
      });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "이전 대화를 불러오지 못했습니다.");
    } finally {
      loadingOlderRef.current = false;
      setLoadingOlder(false);
    }
  }

  function handleScroll() {
    const viewport = viewportRef.current;
    if (!viewport) return;
    const nearBottom = viewport.scrollHeight - viewport.scrollTop - viewport.clientHeight < 80;
    stayAtBottomRef.current = nearBottom;
    setShowLatest(!nearBottom);
    if (viewport.scrollTop < 32) void loadOlder();
  }

  return (
    <section className="practice-chat" role="tabpanel" aria-label="지금까지의 대화">
      <header className="practice-chat__header">
        <div>
          <p>계약 대화</p>
          <h2>지금까지의 대화</h2>
        </div>
        <div className="practice-chat__header-actions">
          <span>{items.length}개 답변</span>
          {onClose && (
            <button type="button" className="secondary practice-chat__close" onClick={onClose} aria-label="이전 대화 닫기">닫기</button>
          )}
        </div>
      </header>
      <div
        className="practice-chat__viewport"
        ref={viewportRef}
        onScroll={handleScroll}
        aria-live="polite"
        aria-relevant="additions"
      >
        <div className="practice-chat__older">
          {hasMore && (
            <button type="button" className="text-link" disabled={loadingOlder} onClick={() => void loadOlder()}>
              {loadingOlder ? "이전 대화를 불러오는 중…" : "이전 대화 불러오기"}
            </button>
          )}
          {!hasMore && items.length > 0 && <span>대화의 시작입니다</span>}
        </div>
        <ol className="practice-chat__messages">
          {items.map((item, index) => (
            <li className="practice-chat__turn" key={item.practice_turn_id}>
              {index === 0 && (
                <MessageBubble sender="counterparty" label="공인중개사" content={item.prompt} />
              )}
              <MessageBubble
                sender="user"
                label="나"
                content={item.timed_out ? "답변하지 못했어요." : item.user_answer ?? "답변을 건너뛰었어요."}
              />
              {item.dialogue_response && (
                <MessageBubble sender="counterparty" label="공인중개사" content={item.dialogue_response} />
              )}
            </li>
          ))}
          {currentTurn && items.length === 0 && (
            <li className="practice-chat__turn practice-chat__turn--current" key={`current-${currentTurn.turn_id}`}>
              <MessageBubble sender="counterparty" label="공인중개사" content={currentTurn.prompt} current />
            </li>
          )}
        </ol>
        {items.length === 0 && !currentTurn && <p className="practice-chat__empty">저장된 대화가 없습니다.</p>}
        {error && <p className="notice practice-chat__error" role="alert">{error}</p>}
      </div>
      {showLatest && (
        <button type="button" className="secondary practice-chat__latest" onClick={() => scrollToBottom("smooth")}>
          최신 대화로 이동
        </button>
      )}
    </section>
  );
}

function MessageBubble({
  sender,
  label,
  content,
  current = false,
}: {
  sender: "counterparty" | "user";
  label: string;
  content: string;
  current?: boolean;
}) {
  return (
    <div className={`practice-chat__message practice-chat__message--${sender}${current ? " practice-chat__message--current" : ""}`}>
      <strong>{label}</strong>
      <p>{content}</p>
    </div>
  );
}
