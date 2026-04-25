"use client";

import type { BaseCase, PortfolioSnapshot } from "@/lib/types";

import { BaseCaseHeadline } from "./BaseCaseHeadline";
import { PortfolioTreemap } from "./PortfolioTreemap";
import { useAppStore } from "@/store/use-app-store";

interface Props {
  baseCase: BaseCase;
  portfolio: PortfolioSnapshot;
  stalePortfolio?: boolean;
}

export function SummaryStrip({ baseCase, portfolio, stalePortfolio }: Props) {
  const judgements = useAppStore((s) => s.brief?.judgements ?? []);

  return (
    <div className="flex gap-8">
      <PortfolioTreemap snapshot={portfolio} stale={stalePortfolio} />
      <BaseCaseHeadline baseCase={baseCase} judgements={judgements} />
    </div>
  );
}
