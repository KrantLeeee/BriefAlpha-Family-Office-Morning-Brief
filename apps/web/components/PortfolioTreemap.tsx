"use client";

import type { PortfolioSnapshot, PortfolioTile } from "@/lib/types";
import { TrendIcon } from "./TrendIcon";

const COLOR_MAP: Record<string, string> = {
  "treemap.nvda": "bg-treemap-nvda text-canvas",
  "treemap.tencent": "bg-treemap-tencent text-canvas",
  "treemap.aapl": "bg-treemap-aapl text-canvas",
  "treemap.msft": "bg-treemap-msft text-ink-900",
  "treemap.tlt": "bg-treemap-tlt text-canvas",
  "treemap.baba": "bg-treemap-baba text-ink-900",
  "treemap.gld": "bg-treemap-gld text-ink-900",
  "treemap.cash": "bg-treemap-cash text-ink-700",
  "treemap.tsla": "bg-treemap-tsla text-canvas",
  "treemap.mtn": "bg-treemap-mtn text-ink-900",
};

const ROW0_HEIGHT = 152;
const ROW1_HEIGHT = 126;
const TREE_TOTAL_WIDTH = 640;
const TREE_TOTAL_HEIGHT = ROW0_HEIGHT + ROW1_HEIGHT;

function tileColorClass(token: string): string {
  return COLOR_MAP[token] ?? "bg-ink-300 text-canvas";
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
      className={`${tileColorClass(tile.color)} ${radius} absolute flex flex-col justify-end p-[10px]`}
      style={{
        left: `${tile.col_start}px`,
        top: `${top}px`,
        width: `${tile.col_span}px`,
        height: `${height}px`,
      }}
    >
      <div className="flex items-baseline gap-[6px] font-mono text-[11px] font-medium leading-tight">
        <span>{tileLabel(tile)}</span>
        <span className="opacity-80">{tile.weight_pct}</span>
      </div>
      <div className="mt-[2px] flex items-baseline gap-[4px] font-mono text-[10px]">
        <TrendIcon trend={tile.trend} className="text-[10px]" />
        <span>{tile.change_pct}</span>
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
        <span className="text-label">关注列表</span>
        <span className="font-mono text-[10px] text-ink-500">{snapshot.watchlist_summary}</span>
      </div>
    </div>
  );
}
