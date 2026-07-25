import type { AsyncRunStatus } from "../types/api";

/** Temporary local MVP ceiling; split by environment after production timing is measured. */
export const LOCAL_MVP_POLL_TIMEOUT_MS = 300_000;
export const POLL_INTERVAL_MS = 1_000;
/** 처음에는 1초 간격으로 묻고, 이 시간이 지나면 간격을 늘려 요청 수를 줄인다. */
export const POLL_BACKOFF_AFTER_MS = 10_000;
export const POLL_BACKOFF_INTERVAL_MS = 3_000;
/** 서버 응답이 연속으로 이만큼 실패하면 기다림을 멈추고 사용자에게 알린다. */
export const POLL_MAX_CONSECUTIVE_FAILURES = 3;

export class PollTimeoutError extends Error {
  constructor() {
    super("처리가 예상보다 오래 걸리고 있습니다.");
    this.name = "PollTimeoutError";
  }
}

interface Pollable {
  status: AsyncRunStatus;
}

interface PollUntilTerminalOptions<T extends Pollable> {
  initialValue: T;
  poll: () => Promise<T>;
  signal?: AbortSignal;
  onUpdate?: (value: T) => void;
  intervalMs?: number;
  timeoutMs?: number;
  isTerminal?: (value: T) => boolean;
}

function abortError() {
  return new DOMException("Polling was aborted.", "AbortError");
}

function isAbort(error: unknown) {
  return error instanceof DOMException && error.name === "AbortError";
}

function wait(ms: number, signal?: AbortSignal) {
  return new Promise<void>((resolve, reject) => {
    if (signal?.aborted) {
      reject(abortError());
      return;
    }
    const onAbort = () => {
      window.clearTimeout(timer);
      reject(abortError());
    };
    const timer = window.setTimeout(() => {
      signal?.removeEventListener("abort", onAbort);
      resolve();
    }, ms);
    signal?.addEventListener("abort", onAbort, { once: true });
  });
}

/**
 * 서버가 pending·running을 계속 돌려주는 동안에는 기다린다. 실제 분석은 상용 LLM·RAG 호출
 * 때문에 1분을 넘길 수 있으므로 짧은 시간 상한으로 끊지 않는다. 응답 자체가 연속으로 실패할
 * 때와 안전 상한(timeoutMs)을 넘겼을 때만 멈춘다.
 */
export async function pollUntilTerminal<T extends Pollable>({
  initialValue,
  poll,
  signal,
  onUpdate,
  intervalMs = POLL_INTERVAL_MS,
  timeoutMs = LOCAL_MVP_POLL_TIMEOUT_MS,
  isTerminal = (current) => current.status === "completed" || current.status === "failed",
}: PollUntilTerminalOptions<T>): Promise<T> {
  const startedAt = Date.now();
  let value = initialValue;
  let consecutiveFailures = 0;
  onUpdate?.(value);

  while (!isTerminal(value)) {
    if (signal?.aborted) throw abortError();
    const elapsed = Date.now() - startedAt;
    const remainingMs = timeoutMs - elapsed;
    if (remainingMs <= 0) throw new PollTimeoutError();
    const nextInterval = elapsed >= POLL_BACKOFF_AFTER_MS
      ? Math.max(intervalMs, POLL_BACKOFF_INTERVAL_MS)
      : intervalMs;
    await wait(Math.min(nextInterval, remainingMs), signal);
    if (Date.now() - startedAt >= timeoutMs) throw new PollTimeoutError();
    try {
      value = await poll();
      consecutiveFailures = 0;
    } catch (caught) {
      if (isAbort(caught) || signal?.aborted) throw caught;
      consecutiveFailures += 1;
      if (consecutiveFailures >= POLL_MAX_CONSECUTIVE_FAILURES) throw caught;
      continue;
    }
    if (signal?.aborted) throw abortError();
    onUpdate?.(value);
  }

  return value;
}
