/**
 * Local-only analytics SDK.
 *
 * Per PRD §5.3: events stay on-host, are forwarded to /api/_analytics, and
 * are stored alongside audit_log so admin diagnostics can query them.
 * Never serialize to localStorage / cookies / external endpoints.
 */
import { useEffect, useMemo } from "react";

export interface AnalyticsEvent {
  event: string;
  brief_id?: string;
  judgement_id?: string;
  duration_ms?: number;
  close_method?: "esc" | "outside_click" | "back" | "explicit";
  cited_count?: number;
  validation_passed?: boolean;
  [key: string]: unknown;
}

const QUEUE: AnalyticsEvent[] = [];
let FLUSH_TIMER: ReturnType<typeof setTimeout> | null = null;

function flush() {
  if (typeof window === "undefined") return;
  if (QUEUE.length === 0) return;
  const batch = QUEUE.splice(0, QUEUE.length);
  navigator.sendBeacon?.(
    "/api/_analytics",
    new Blob([JSON.stringify({ events: batch })], { type: "application/json" })
  );
}

export function track(evt: AnalyticsEvent): void {
  QUEUE.push({ ...evt, ts: new Date().toISOString() });
  if (FLUSH_TIMER) clearTimeout(FLUSH_TIMER);
  FLUSH_TIMER = setTimeout(flush, 500);
}

/**
 * React helper that fires a `mount` event on first render and the supplied
 * `onUnmount` event with `duration_ms` set when the component unmounts.
 *
 * The deps array uses a memoized JSON serialization of `payload` because
 * tracked sessions intentionally re-fire whenever any payload field
 * changes; depending on the object reference would re-fire on every
 * render, while listing each field would force callers to know our
 * implementation. The memo keeps the rule clean for exhaustive-deps.
 */
export function useTrackedSession(
  enterEventName: string,
  exitEventName: string,
  payload: Omit<AnalyticsEvent, "event" | "duration_ms">
) {
  const payloadKey = useMemo(() => JSON.stringify(payload), [payload]);
  useEffect(() => {
    const enteredAt = Date.now();
    track({ event: enterEventName, ...payload });
    return () => {
      track({
        event: exitEventName,
        ...payload,
        duration_ms: Date.now() - enteredAt,
      });
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enterEventName, exitEventName, payloadKey]);
}
