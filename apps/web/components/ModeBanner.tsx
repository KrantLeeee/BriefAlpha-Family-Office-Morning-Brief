"use client";

import * as React from "react";

import type { SystemMeta } from "@/lib/types";

interface Props {
  system: SystemMeta;
}

export function ModeBanner({ system }: Props) {
  const [showHint, setShowHint] = React.useState(false);
  // Hidden when live mode is healthy — no banner.
  if (system.mode === "live" && system.status === "ready") return null;

  const { bg, text, hint } = renderConfig(system);
  return (
    <div
      role="status"
      className="w-full px-8 py-2 font-mono text-[11px] text-ink-700"
      style={{ backgroundColor: bg }}
    >
      <span>{text}</span>
      {hint && (
        <button
          type="button"
          className="ml-3 underline decoration-dotted underline-offset-2 hover:opacity-70"
          onClick={() => setShowHint((v) => !v)}
          aria-expanded={showHint}
          title={hint}
        >
          如何切到真实管线 (?)
        </button>
      )}
      {hint && showHint && <span className="ml-3 text-ink-500">{hint}</span>}
    </div>
  );
}

function renderConfig(system: SystemMeta): { bg: string; text: string; hint?: string } {
  if (system.mode === "demo") {
    return {
      bg: "#FFF1E6",
      text: "示例数据 · 未配置真实数据源（BRIEFALPHA_MODE=demo）",
      // Tooltip-only hint — no navigation. The Next app does not serve
      // /README, and a 404 here would directly contradict the trust-loop
      // promise. Detailed instructions live in README "切换模式".
      hint: "切到真实管线：export BRIEFALPHA_MODE=live + ANTHROPIC_API_KEY (或 OPENAI_API_KEY) + packages/config/data_sources.yml 的 sec.user_agent。详见 README 切换模式 章节。",
    };
  }
  // mode === "live" beyond this point
  if (system.status === "generating") {
    return {
      bg: "#E0F2FE",
      text: "正在生成今日 brief…（首次启动可能需要 30-60 秒）",
    };
  }
  if (system.status === "stale") {
    return {
      bg: "#F1F5F9",
      text: "显示昨日数据 · 今日 brief 尚未生成",
    };
  }
  // status === "error"
  return {
    bg: "#FEE2E2",
    text: "数据获取失败 · 请稍后重试或检查后台日志",
  };
}
