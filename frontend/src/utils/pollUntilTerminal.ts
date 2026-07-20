import type { AsyncRunStatus } from "../types/api";

/** Temporary local MVP ceiling; split by environment after production timing is measured. */
export const LOCAL_MVP_POLL_TIMEOUT_MS = 60_000;
export const POLL_INTERVAL_MS = 1_000;

export class PollTimeoutError extends Error {
  constructor() {
    super("\uCC98\uB9AC\uAC00 \uC608\uC0C1\uBCF4\uB2E4 \uC624\uB798 \uAC78\uB9AC\uACE0 \uC788\uC2B5\uB2C8\uB2E4.");
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
  onUpdate?.(value);

  while (!isTerminal(value)) {
    if (signal?.aborted) throw abortError();
    const remainingMs = timeoutMs - (Date.now() - startedAt);
    if (remainingMs <= 0) throw new PollTimeoutError();
    await wait(Math.min(intervalMs, remainingMs), signal);
    if (Date.now() - startedAt >= timeoutMs) throw new PollTimeoutError();
    value = await poll();
    if (signal?.aborted) throw abortError();
    onUpdate?.(value);
  }

  return value;
}
