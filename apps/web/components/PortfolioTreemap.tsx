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

const ROW_HEIGHTS: Record<0 | 1, number> = { 0: 152, 1: 126 };
const TREE_TOTAL_WIDTH = 640;

function tileColorClass(token: string): string {
  return COLOR_MAP[token] ?? "bg-ink-300 text-canvas";
}

function tileLabel(t: PortfolioTile): string {
  return t.label ?? t.ticker;
}

function Tile({ tile }: { tile: PortfolioTile }) {
  const isFirstRow = tile.row === 0;
  const radiusClasses = (() => {
    if (isFirstRow && tile.col_start === 0) return "rounded-tl-card";
    if (isFirstRow && tile.col_start + tile.col_span >= TREE_TOTAL_WIDTH) return "rounded-tr-card";
    if (!isFirstRow && tile.col_start === 0) return "rounded-bl-card";
    if (!isFirstRow && tile.col_start + tile.col_span >= TREE_TOTAL_WIDTH) return "rounded-br-card";
    return "";
  })();

  return (
    <div
      role="img"
      aria-label={`${tileLabel(tile)} 占比 ${tile.weight_pct}，隔夜 ${tile.change_pct}`}
      className={`${tileColorClass(tile.color)} ${radiusClasses} flex h-full flex-col justify-end p-[10px]`}
      style={{ width: `${tile.col_span}px`, height: `${ROW_HEIGHTS[tile.row]}px` }}
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
  const row0 = snapshot.tiles.filter((t) => t.row === 0).sort((a, b) => a.col_start - b.col_start);
  const row1 = snapshot.tiles.filter((t) => t.row === 1).sort((a, b) => a.col_start - b.col_start);

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
        style={{ width: `${TREE_TOTAL_WIDTH}px`, height: `${ROW_HEIGHTS[0] + ROW_HEIGHTS[1] + 4}px` }}
      >
        <div className="flex" style={{ gap: "0px" }}>
          <div className="flex" style={{ gap: 4 }}>
            {row0.map((t) => (
              <Tile key={t.ticker} tile={t} />
            ))}
          </div>
        </div>
        <div className="mt-1 flex" style={{ gap: 4 }}>
          {row1.map((t) => (
            <Tile key={t.ticker} tile={t} />
          ))}
        </div>
        {stale && (
          <div className="absolute inset-0 flex items-center justify-center bg-canvas/60 backdrop-blur-[2px]">
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
