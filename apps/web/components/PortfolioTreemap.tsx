"use client";

import type { PortfolioSnapshot, PortfolioTile } from "@/lib/types";
import { TrendIcon } from "./TrendIcon";

const ROW0_HEIGHT = 152;
const ROW1_HEIGHT = 126;
const TREE_TOTAL_WIDTH = 640;
const TREE_TOTAL_HEIGHT = ROW0_HEIGHT + ROW1_HEIGHT;

function tileColorClass(tile: PortfolioTile): string {
  const magnitude = Math.abs(parsePct(tile.change_pct));
  if (tile.trend === "up") {
    if (magnitude >= 2.5) return "bg-[#14532D] text-white";
    if (magnitude >= 1) return "bg-[#15803D] text-white";
    return "bg-treemap-mtn text-ink-900";
  }
  if (tile.trend === "down") {
    if (magnitude >= 2.5) return "bg-treemap-nvda text-white";
    if (magnitude >= 1) return "bg-treemap-aapl text-ink-900";
    return "bg-treemap-msft text-ink-900";
  }
  return "bg-treemap-cash text-ink-900";
}

function parsePct(value: string): number {
  const n = Number.parseFloat(value.replace("%", ""));
  return Number.isFinite(n) ? n : 0;
}

function tileLabel(t: PortfolioTile): string {
  return t.label ?? t.ticker;
}

/**
 * Tiles use absolute positioning matching the Pencil canvas exactly:
 * row 0 sums to 640 (NVDA 209 + 0700 175 + AAPL 140 + MSFT 116) and row 1
 * sums to 640 (TLT 142 + BABA 114 + GLD 114 + CASH 128 + TSLA 71 + MTN 71).
 * No inter-tile gap — the canvas has continuous color blocks, and the
 * outer rounded corners come from the four corner tiles only. This is
 * what fills the right edge that flex+gap was leaking.
 */
function Tile({ tile }: { tile: PortfolioTile }) {
  const isFirstRow = tile.row === 0;
  const isNarrow = tile.col_span < 92;
  const top = isFirstRow ? 0 : ROW0_HEIGHT;
  const height = isFirstRow ? ROW0_HEIGHT : ROW1_HEIGHT;
  const right = tile.col_start + tile.col_span;

  const radius =
    [
      isFirstRow && tile.col_start === 0 ? "rounded-tl-card" : "",
      isFirstRow && right >= TREE_TOTAL_WIDTH ? "rounded-tr-card" : "",
      !isFirstRow && tile.col_start === 0 ? "rounded-bl-card" : "",
      !isFirstRow && right >= TREE_TOTAL_WIDTH ? "rounded-br-card" : "",
    ]
      .filter(Boolean)
      .join(" ");

  return (
    <div
      role="img"
      aria-label={`${tileLabel(tile)} 占比 ${tile.weight_pct}，隔夜 ${tile.change_pct}`}
      className={`${tileColorClass(tile)} ${radius} absolute flex flex-col justify-end overflow-hidden p-[10px]`}
      style={{
        left: `${tile.col_start}px`,
        top: `${top}px`,
        width: `${tile.col_span}px`,
        height: `${height}px`,
      }}
    >
      <div
        className={[
          "min-w-0 font-mono font-medium leading-tight",
          isNarrow
            ? "flex flex-col gap-[1px] text-[10px]"
            : "flex items-baseline gap-[6px] text-[11px]",
        ].join(" ")}
      >
        <span className="truncate">{tileLabel(tile)}</span>
        <span className="truncate opacity-80">{tile.weight_pct}</span>
      </div>
      <div className="mt-[2px] flex min-w-0 items-baseline gap-[4px] font-mono text-[10px]">
        <TrendIcon trend={tile.trend} className="!text-current text-[10px]" />
        <span className="truncate">{tile.change_pct}</span>
      </div>
    </div>
  );
}

export function PortfolioTreemap({ snapshot, stale }: { snapshot: PortfolioSnapshot; stale?: boolean }) {
  return (
    <div className="flex w-[640px] flex-col gap-3" aria-labelledby="portfolio-heading">
      <div className="flex items-center justify-between">
        <span id="portfolio-heading" className="text-label">
          持仓全景
        </span>
        <span className="text-label font-normal">面积=持仓权重 · ▲▼=隔夜变动</span>
      </div>

      <div
        className="relative"
        style={{ width: `${TREE_TOTAL_WIDTH}px`, height: `${TREE_TOTAL_HEIGHT}px` }}
      >
        {snapshot.tiles.map((t) => (
          <Tile key={t.ticker} tile={t} />
        ))}
        {stale && (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-canvas/60 backdrop-blur-[2px]">
            <span className="rounded-chip bg-canvas/90 px-3 py-1 font-mono text-[11px] text-ink-500">
              持仓快照不可用 — 显示上一日 brief
            </span>
          </div>
        )}
      </div>

      <div className="flex items-center gap-2 border-t border-line py-[6px]">
        <span className="text-label">市场参照（非持仓）</span>
        <span
          aria-label="非组合持仓但持续关注的标的，用作市场背景参考。点击编辑（即将上线）。"
          title="非组合持仓但持续关注的标的，用作市场背景参考。点击编辑（即将上线）。"
          className="cursor-help font-mono text-[10px] text-ink-400"
        >
          (?)
        </span>
        <span className="font-mono text-[10px] text-ink-500">{snapshot.watchlist_summary}</span>
      </div>
    </div>
  );
}
