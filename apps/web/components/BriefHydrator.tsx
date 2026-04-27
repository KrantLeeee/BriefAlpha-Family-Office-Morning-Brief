"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import type { Brief } from "@/lib/types";
import { useAppStore } from "@/store/use-app-store";

// First-boot UX: lifespan kicks off background brief generation; the first
// /api/brief/today response is the stale fixture (system.status === "generating").
// Without auto-refresh the user has to manually reload until the live brief
// lands — they reported "等了几分钟". We poll every 30s while generating, and
// stop the moment status flips to ready/stale/error so we never run a
// silent forever-loop in healthy state.
const POLL_MS = 30_000;

export function BriefHydrator({ brief }: { brief: Brief }) {
  const setBrief = useAppStore((s) => s.setBrief);
  const router = useRouter();
  useEffect(() => {
    setBrief(brief);
  }, [brief, setBrief]);

  useEffect(() => {
    if (brief.system.status !== "generating") return;
    const id = window.setInterval(() => router.refresh(), POLL_MS);
    return () => window.clearInterval(id);
  }, [brief.system.status, router]);

  return null;
}
