import type { PlaybookEvent } from "@/lib/types";

const ROW_GAP = 24;

/**
 * 今日观察事件 — frame fFOSV / Today Playbook timeline.
 *
 * Vertical stack (top → bottom). The shared rail and the circle markers
 * share the marker column's center axis: rail uses `left-1/2 -translate-x-1/2`
 * inside the same column the circle is `justify-center`-ed in, guaranteeing
 * concentric alignment regardless of column width.
 */
export function TodayPlaybook({ events }: { events: PlaybookEvent[] }) {
  const next = events.find((e) => e.is_next) ?? events[0];

  return (
    <section
      aria-labelledby="playbook-heading"
      className="border-b bg-surface"
      style={{ borderColor: "#dfe3e8" }}
    >
      <div className="mx-auto max-w-[1440px] px-8 py-6">
        <div className="flex items-center justify-between">
          <span id="playbook-heading" className="text-label">
            今日观察事件
          </span>
          {next && (
            <span className="font-mono text-[11px] font-bold text-ink-900">
              下一事件 {next.time_hkt} HKT · {next.relative_time_hkt}
            </span>
          )}
        </div>

        <ol className="mt-3 flex flex-col border-y border-line py-6">
          {events.map((event, idx) => {
            const isLast = idx === events.length - 1;
            return (
              <li
                key={event.time_hkt}
                className="grid grid-cols-[110px_24px_1fr] items-start gap-3"
                style={{ paddingBottom: isLast ? 0 : ROW_GAP }}
              >
                <div className="flex flex-col">
                  <span className="font-mono text-[12px] text-ink-900">
                    {event.time_hkt} HKT
                  </span>
                  <span
                    className={[
                      "font-mono text-[10px]",
                      event.is_next ? "text-orange-600" : "text-ink-500",
                    ].join(" ")}
                  >
                    {event.relative_time_hkt}
                  </span>
                </div>

                {/*
                 * Marker column: circle + rail share `left-1/2 -translate-x-1/2`.
                 * Rail extends from below the circle to the bottom of the
                 * row (incl. paddingBottom = ROW_GAP), so it visually links
                 * to the next item's circle.
                 */}
                <div className="relative flex h-full justify-center">
                  <span
                    aria-hidden
                    className="z-10 mt-[6px] inline-block h-[11px] w-[11px] rounded-full border-[1.5px] border-ink-700 bg-canvas"
                  />
                  {!isLast && (
                    <span
                      aria-hidden
                      className="absolute left-1/2 top-[17px] w-px -translate-x-1/2 bg-line"
                      style={{ bottom: -ROW_GAP }}
                    />
                  )}
                </div>

                <div className="flex flex-col gap-1">
                  <span className="font-sans text-[15px] font-medium text-ink-900">
                    {event.label}
                  </span>
                  <span className="font-sans text-[12px] text-ink-500">
                    {event.detail}
                  </span>
                </div>
              </li>
            );
          })}
        </ol>
      </div>
    </section>
  );
}
