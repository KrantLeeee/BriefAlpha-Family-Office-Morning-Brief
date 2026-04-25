import type { Trend } from "@/lib/types";

const SYMBOL: Record<Trend, string> = {
  up: "▲",
  down: "▼",
  flat: "■",
};

const ARIA: Record<Trend, string> = {
  up: "上涨",
  down: "下跌",
  flat: "持平",
};

const COLOR_CLASS: Record<Trend, string> = {
  up: "text-success",
  down: "text-danger",
  flat: "text-ink-500",
};

/**
 * Accessible trend indicator: outputs ▲ / ▼ / ■ + color + aria-label so
 * direction is conveyed by symbol and color jointly (per design.md §7).
 */
export function TrendIcon({
  trend,
  className = "",
}: {
  trend: Trend;
  className?: string;
}) {
  return (
    <span
      role="img"
      aria-label={ARIA[trend]}
      className={`${COLOR_CLASS[trend]} ${className}`}
    >
      {SYMBOL[trend]}
    </span>
  );
}
