import type { PlaybookEvent } from "@/lib/types";

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
          <span id="playbook-heading" className="text-label" style={{ fontFamily: "var(--font-jetbrains)" }}>
            今日观察事件
          </span>
          {next && (
            <span className="font-mono text-[11px] font-bold text-ink-900">
              下一事件 {next.time_hkt} HKT · {next.relative_time_hkt}
            </span>
          )}
        </div>

        <ol className="relative mt-3 grid grid-cols-1 gap-6 border-y border-line py-6 sm:grid-cols-2">
          {events.map((event) => (
            <li key={event.time_hkt} className="grid grid-cols-[88px_24px_1fr] items-start gap-3">
              <div className="flex flex-col">
                <span className="font-mono text-[12px] text-ink-900">{event.time_hkt} HKT</span>
                <span
                  className={[
                    "font-mono text-[10px]",
                    event.is_next ? "text-orange-600" : "text-ink-500",
                  ].join(" ")}
                >
                  {event.relative_time_hkt}
                </span>
              </div>

              <div className="relative h-full">
                <span
                  aria-hidden
                  className="absolute left-1/2 top-1 inline-block h-3 w-3 -translate-x-1/2 rounded-full border border-ink-700 bg-canvas"
                />
                <span aria-hidden className="absolute left-1/2 top-4 h-full w-px -translate-x-1/2 bg-line" />
              </div>

              <div className="flex flex-col">
                <span className="font-sans text-[15px] font-medium text-ink-900">{event.label}</span>
                <span className="font-sans text-[12px] text-ink-500">{event.detail}</span>
              </div>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
