/**
 * Local-only analytics SDK.
 *
 * Per PRD §5.3: events stay on-host, are forwarded to /api/_analytics, and
 * are stored alongside audit_log so admin diagnostics can query them.
 * Never serialize to localStorage / cookies / external endpoints.
 */
import { useEffect } from "react";

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
 */
export function useTrackedSession(
  enterEventName: string,
  exitEventName: string,
  payload: Omit<AnalyticsEvent, "event" | "duration_ms">
) {
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
  }, [enterEventName, exitEventName, JSON.stringify(payload)]);
}
