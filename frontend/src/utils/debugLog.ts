/**
 * 디버깅 데모 영상용 실시간 로그 버스.
 *
 * `?debug=1`이 붙은 주소에서만 수집·표시한다. 평소 화면에는 아무 영향이 없다.
 * 개인정보 원칙: 인식된 문장·답변 본문은 넣지 않는다. 시간(ms)·개수만 남긴다.
 */

export type DebugChannel = "STT" | "LLM" | "TTS" | "VIDEO" | "UI" | "API";

export interface DebugLogEntry {
  id: number;
  at: string;
  channel: DebugChannel;
  message: string;
}

const MAX_ENTRIES = 200;

let entries: DebugLogEntry[] = [];
let nextId = 1;
const listeners = new Set<(items: DebugLogEntry[]) => void>();

const DEBUG_STORAGE_KEY = "lease-companion:debug-overlay";

/**
 * `?debug=1`을 한 번 붙이면 그 탭에서는 계속 켜져 있다.
 *
 * 화면을 이동하면 쿼리 문자열이 사라지므로 sessionStorage에 붙잡아 둔다.
 * 끄려면 `?debug=0`을 붙이거나 탭을 닫는다.
 */
export function isDebugOverlayEnabled(): boolean {
  if (typeof window === "undefined") return false;
  const param = new URLSearchParams(window.location.search).get("debug");
  const requestedOn = param !== null && param !== "0" && param !== "false";
  try {
    if (param !== null) {
      if (requestedOn) window.sessionStorage.setItem(DEBUG_STORAGE_KEY, "1");
      else window.sessionStorage.removeItem(DEBUG_STORAGE_KEY);
      return requestedOn;
    }
    return window.sessionStorage.getItem(DEBUG_STORAGE_KEY) === "1";
  } catch {
    // 사생활 보호 모드 등에서 storage가 막히면 쿼리 파라미터만 본다.
    return requestedOn;
  }
}

function timestamp(): string {
  const now = new Date();
  const pad = (value: number, size = 2) => String(value).padStart(size, "0");
  return `${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}.${pad(now.getMilliseconds(), 3)}`;
}

export function debugLog(channel: DebugChannel, message: string): void {
  if (!isDebugOverlayEnabled()) return;
  const entry: DebugLogEntry = { id: nextId++, at: timestamp(), channel, message };
  entries = [...entries, entry].slice(-MAX_ENTRIES);
  listeners.forEach((listener) => listener(entries));
  // 콘솔에도 남겨 브라우저 개발자도구 녹화에서 함께 보이게 한다.
  console.info(`[${entry.at}] [${channel}] ${message}`);
}

export function subscribeDebugLog(listener: (items: DebugLogEntry[]) => void): () => void {
  listeners.add(listener);
  listener(entries);
  return () => {
    listeners.delete(listener);
  };
}

export function clearDebugLog(): void {
  entries = [];
  listeners.forEach((listener) => listener(entries));
}

/**
 * 화면 렌더링 FPS와 끊김 구간을 계측한다.
 *
 * 립싱크 생성 FPS(`effective_fps`)와는 다른 값이다. 이쪽은 브라우저가 실제로
 * 그려낸 프레임 수이며, 계약 점검 화면이 느려지는 구간을 로그로 남기기 위한 것이다.
 * `?debug=1`이 아니면 아무 것도 하지 않는다.
 */
export function startRenderFpsProbe(
  onSample: (fps: number) => void,
  options: { slowFpsThreshold?: number; longTaskMs?: number } = {},
): () => void {
  if (!isDebugOverlayEnabled() || typeof window === "undefined") return () => {};
  const slowFps = options.slowFpsThreshold ?? 45;
  const longTaskMs = options.longTaskMs ?? 120;

  let frames = 0;
  let windowStartedAt = performance.now();
  let rafId = 0;
  let running = true;
  // 라우터에 결합하지 않고 경로 변화를 감지한다. 오버레이가 살아 있다는 신호도 된다.
  let lastPath = `${window.location.pathname}${window.location.search}`;
  debugLog("UI", `오버레이 시작 path=${lastPath}`);

  const tick = () => {
    if (!running) return;
    frames += 1;
    const now = performance.now();
    const elapsed = now - windowStartedAt;
    if (elapsed >= 1000) {
      const fps = Math.round((frames * 1000) / elapsed);
      onSample(fps);
      // 매 초 로그를 남기면 화면이 도배된다. 느려진 구간만 기록한다.
      if (fps < slowFps) debugLog("UI", `렌더 지연 fps=${fps} (기준 ${slowFps} 미만)`);
      const path = `${window.location.pathname}${window.location.search}`;
      if (path !== lastPath) {
        debugLog("UI", `화면 이동 path=${path} fps=${fps}`);
        lastPath = path;
      }
      frames = 0;
      windowStartedAt = now;
    }
    rafId = window.requestAnimationFrame(tick);
  };
  rafId = window.requestAnimationFrame(tick);

  // 메인 스레드를 붙잡은 작업을 직접 집어낸다. 끊김 원인 설명용.
  let observer: PerformanceObserver | null = null;
  if (typeof PerformanceObserver !== "undefined") {
    try {
      observer = new PerformanceObserver((list) => {
        list.getEntries().forEach((entry) => {
          if (entry.duration >= longTaskMs) {
            debugLog("UI", `메인 스레드 blocking ${Math.round(entry.duration)}ms (${entry.name})`);
          }
        });
      });
      observer.observe({ entryTypes: ["longtask"] });
    } catch {
      observer = null;
    }
  }

  return () => {
    running = false;
    window.cancelAnimationFrame(rafId);
    observer?.disconnect();
  };
}

/** 미디어 잡 응답의 타이밍 지표를 한 줄로 요약한다. */
export function formatMediaMetrics(metrics: Record<string, unknown> | null | undefined): string {
  if (!metrics) return "지표 없음";
  const timings = (metrics.timings_ms ?? {}) as Record<string, unknown>;
  const parts = [
    timings.tts !== undefined ? `tts=${timings.tts}ms` : null,
    timings.video !== undefined ? `video=${timings.video}ms` : null,
    metrics.generated_frames !== undefined ? `frames=${metrics.generated_frames}` : null,
    metrics.effective_fps !== undefined ? `fps=${metrics.effective_fps}` : null,
    metrics.video_encoder !== undefined ? `encoder=${metrics.video_encoder}` : null,
    timings.end_to_end !== undefined ? `e2e=${timings.end_to_end}ms` : null,
    metrics.target_met !== undefined ? `target_met=${metrics.target_met}` : null,
    metrics.video_disabled === true ? "video=disabled" : null,
  ].filter(Boolean);
  return parts.length > 0 ? parts.join(" ") : "지표 없음";
}
