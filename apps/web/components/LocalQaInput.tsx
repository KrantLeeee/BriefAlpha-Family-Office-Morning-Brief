"use client";

import * as React from "react";
import { useEffect, useState, useTransition } from "react";

import { postQa } from "@/lib/api";
import type { QaResponse } from "@/lib/types";
import { useAppStore } from "@/store/use-app-store";

interface Props {
  briefId: string;
  scope: "judgement" | "evidence" | "global";
  scopeTargetId?: string;
  suggestedQuestions: string[];
}

const QA_TIMEOUT_MS = 20_000;
const MAX_QUESTION_LEN = 500;

function DemoAnswerBadge() {
  return (
    <span className="inline-flex items-center gap-1 rounded-chip border border-orange-200 bg-warningWash px-2 py-[2px] font-mono text-[10px] font-medium text-orange-600">
      示例回答
    </span>
  );
}

function failureLabel(reason: string | undefined): string {
  switch (reason) {
    case "demo_mode_prebaked":
      return "示例回答（基于 demo brief）";
    case "demo_mode_no_match":
      return "提示";
    case "evidence_insufficient":
      return "证据不足";
    case "out_of_scope":
      return "超出范围";
    case "empty_question":
      return "提示";
    case "llm_unconfigured":
      return "QA 暂不可用";
    case "brief_expired":
      return "Brief 已过期";
    default:
      return "回答（已校验）";
  }
}

export function LocalQaInput({ briefId, scope, scopeTargetId, suggestedQuestions }: Props) {
  const [question, setQuestion] = useState("");
  const [response, setResponse] = useState<QaResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  const setHighlight = useAppStore((s) => s.setHighlightedEvidence);
  const pushQa = useAppStore((s) => s.pushQa);

  useEffect(() => {
    if (!response) return;
    const firstCited = response.cited_evidence_ids[0];
    if (!firstCited) return;
    setHighlight(firstCited);
    const t = setTimeout(() => setHighlight(null), 2000);
    return () => clearTimeout(t);
  }, [response, setHighlight]);

  const submitDisabled = pending || question.trim() === "" || question.length > MAX_QUESTION_LEN;

  async function submit() {
    setError(null);
    setResponse(null);
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), QA_TIMEOUT_MS);
    try {
      const r = await postQa({
        brief_id: briefId,
        scope,
        scope_target_id: scopeTargetId,
        question: question.trim(),
      });
      setResponse(r);
      pushQa({ question: question.trim(), answer: r.answer });
    } catch (e: unknown) {
      setError("无法连接到 QA 服务（网络或后端错误）。请刷新后重试。");
    } finally {
      clearTimeout(timer);
    }
  }

  return (
    <section aria-labelledby="ask-heading" className="flex flex-col gap-3">
      <span id="ask-heading" className="text-label">
        关于此研判提问
      </span>

      <div className="flex h-[42px] items-center justify-between gap-3 rounded-chip border border-line bg-surface px-3">
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value.slice(0, MAX_QUESTION_LEN))}
          placeholder="基于上方证据提问…"
          className="flex-1 bg-transparent font-sans text-[14px] text-ink-900 outline-none"
          aria-describedby="ask-hint"
          maxLength={MAX_QUESTION_LEN}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !submitDisabled) {
              startTransition(submit);
            }
          }}
        />
        <button
          type="button"
          onClick={() => startTransition(submit)}
          disabled={submitDisabled}
          className="font-mono text-[11px] font-medium text-orange-600 disabled:cursor-not-allowed disabled:text-ink-300"
        >
          {pending ? "查询中…" : "提问 ↵"}
        </button>
      </div>

      {suggestedQuestions.length > 0 && (
        <p id="ask-hint" className="whitespace-pre-line font-mono text-[10px] leading-[1.55] text-ink-500">
          {`试试：${suggestedQuestions.map((q) => `· ${q}`).join("\n     ")}`}
        </p>
      )}

      {error && <p className="font-mono text-[11px] text-danger">{error}</p>}

      {response && (
        <div className="flex flex-col gap-2 rounded-card border border-line bg-surface p-3">
          <div className="flex items-center gap-2">
            <span className="text-label">{failureLabel(response.failure_reason)}</span>
            {response.is_demo_response && <DemoAnswerBadge />}
          </div>
          <p className="whitespace-pre-line font-sans text-[13px] leading-[1.55] text-ink-700">
            {formatLongDecimals(response.answer)}
          </p>
          {response.citations.length > 0 && (
            <ul className="flex flex-wrap gap-2">
              {response.citations.map((c) => (
                <li
                  key={c.evidence_id}
                  className="rounded-chip border border-orange-600 px-2 py-[2px] font-mono text-[10px] text-orange-600"
                >
                  {c.label}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      <span className="font-mono text-[10px] text-ink-400">
        回答将基于上方证据；超出范围将提示证据不足而非猜测。
      </span>
    </section>
  );
}

function formatLongDecimals(value: string): string {
  return value.replace(/([+-]?\d+\.\d{3,})/g, (match) => {
    const n = Number.parseFloat(match);
    return Number.isFinite(n) ? n.toFixed(2) : match;
  });
}
