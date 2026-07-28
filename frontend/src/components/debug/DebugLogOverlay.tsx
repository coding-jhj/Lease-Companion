import { useEffect, useRef, useState } from "react";
import {
  clearDebugLog,
  isDebugOverlayEnabled,
  startRenderFpsProbe,
  subscribeDebugLog,
  type DebugLogEntry,
} from "../../utils/debugLog";

const channelColors: Record<string, string> = {
  STT: "#38bdf8",
  UI: "#f87171",
  API: "#60a5fa",
  LLM: "#a78bfa",
  TTS: "#34d399",
  VIDEO: "#fbbf24",
};

/**
 * 디버깅 데모 영상 전용 실시간 로그 패널.
 *
 * 주소에 `?debug=1`이 있을 때만 렌더링한다. 촬영이 끝나면 파라미터만 빼면 되고
 * 코드를 되돌릴 필요가 없다.
 */
export function DebugLogOverlay() {
  const enabled = isDebugOverlayEnabled();
  const [entries, setEntries] = useState<DebugLogEntry[]>([]);
  const [collapsed, setCollapsed] = useState(false);
  const [fps, setFps] = useState<number | null>(null);
  const listRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!enabled) return;
    return subscribeDebugLog(setEntries);
  }, [enabled]);

  useEffect(() => {
    if (!enabled) return;
    return startRenderFpsProbe(setFps);
  }, [enabled]);

  useEffect(() => {
    const node = listRef.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [entries]);

  if (!enabled) return null;

  return (
    <aside
      aria-label="디버그 실시간 로그"
      style={{
        position: "fixed",
        right: 12,
        bottom: 12,
        width: collapsed ? 200 : 460,
        maxWidth: "calc(100vw - 24px)",
        zIndex: 9999,
        background: "rgba(9, 12, 20, 0.94)",
        color: "#e2e8f0",
        border: "1px solid #334155",
        borderRadius: 8,
        fontFamily: "Consolas, 'Cascadia Mono', monospace",
        fontSize: 12,
        boxShadow: "0 8px 24px rgba(0,0,0,0.4)",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "6px 10px",
          borderBottom: collapsed ? "none" : "1px solid #334155",
        }}
      >
        <strong style={{ fontSize: 12, letterSpacing: "0.04em" }}>DEBUG LOG</strong>
        <span
          title="화면 렌더링 FPS (립싱크 생성 fps와 다름)"
          style={{ color: fps === null ? "#64748b" : fps < 45 ? "#f87171" : "#34d399", fontWeight: 700 }}
        >
          {fps === null ? "-- fps" : `${fps} fps`}
        </span>
        <span style={{ color: "#64748b" }}>{entries.length}</span>
        <span style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
          <button
            type="button"
            onClick={() => clearDebugLog()}
            style={{ background: "transparent", color: "#94a3b8", border: "1px solid #334155", borderRadius: 4, padding: "1px 6px", cursor: "pointer" }}
          >
            비우기
          </button>
          <button
            type="button"
            onClick={() => setCollapsed((value) => !value)}
            style={{ background: "transparent", color: "#94a3b8", border: "1px solid #334155", borderRadius: 4, padding: "1px 6px", cursor: "pointer" }}
          >
            {collapsed ? "펼치기" : "접기"}
          </button>
        </span>
      </div>
      {!collapsed && (
        <div ref={listRef} style={{ maxHeight: 260, overflowY: "auto", padding: "6px 10px", display: "flex", flexDirection: "column", gap: 2 }}>
          {entries.length === 0 && <span style={{ color: "#64748b" }}>대기 중… 음성 입력·답변 제출 시 기록됩니다.</span>}
          {entries.map((entry) => (
            <div key={entry.id} style={{ whiteSpace: "pre-wrap", lineHeight: 1.5 }}>
              <span style={{ color: "#64748b" }}>{entry.at}</span>{" "}
              <span style={{ color: channelColors[entry.channel] ?? "#e2e8f0", fontWeight: 700 }}>{entry.channel}</span>{" "}
              <span>{entry.message}</span>
            </div>
          ))}
        </div>
      )}
    </aside>
  );
}
