"use client";

import { useEffect } from "react";

import type { Brief } from "@/lib/types";
import { useAppStore } from "@/store/use-app-store";

export function BriefHydrator({ brief }: { brief: Brief }) {
  const setBrief = useAppStore((s) => s.setBrief);
  useEffect(() => {
    setBrief(brief);
  }, [brief, setBrief]);
  return null;
}
