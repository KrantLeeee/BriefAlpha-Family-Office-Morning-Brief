"use client";

export function MacroPulseCollapsed({
  label,
  expandLabel,
}: {
  label: string;
  expandLabel: string;
}) {
  return (
    <button
      type="button"
      className="flex w-full items-center justify-between border-b py-3"
      style={{ borderColor: "#d7dce2" }}
      onClick={() => {
        // Full macro_pulse UI is part of P2; the entry stays present so the
        // data shape is exposed and a user can request expansion.
      }}
    >
      <div className="flex items-center gap-2">
        <ChevronRight />
        <span className="font-sans text-[13px] font-medium text-ink-700" style={{ fontFamily: "Montserrat, var(--font-inter)" }}>
          {label}
        </span>
      </div>
      <span className="font-mono text-[11px] text-ink-700">{expandLabel}</span>
    </button>
  );
}

function ChevronRight() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#374151" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M9 6l6 6-6 6" />
    </svg>
  );
}
