"use client";

import * as React from "react";

import type { SystemMeta } from "@/lib/types";

interface Props {
  system: SystemMeta;
}

export function ModeBanner({ system }: Props) {
  // Hidden when live mode is healthy — no banner.
  if (system.mode === "live" && system.status === "ready") return null;

  const { bg, text, link } = renderConfig(system);
  return (
    <div
      role="status"
      className="w-full px-8 py-2 font-mono text-[11px] text-ink-700"
      style={{ backgroundColor: bg }}
    >
      <span>{text}</span>
      {link && (
        <a
          href={link.href}
          className="ml-3 underline hover:opacity-70"
        >
          {link.label}
        </a>
      )}
    </div>
  );
}

function renderConfig(system: SystemMeta): { bg: string; text: string; link?: { href: string; label: string } } {
  if (system.mode === "demo") {
    return {
      bg: "#FFF1E6",
      text: "示例数据 · 未配置真实数据源（BRIEFALPHA_MODE=demo）",
      link: { href: "/README#switching-modes", label: "如何切到真实管线" },
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
