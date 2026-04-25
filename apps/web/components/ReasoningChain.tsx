import type { ReasoningChain as ReasoningChainType } from "@/lib/types";

interface Stage {
  label: string;
  text: string;
  emphasized?: boolean;
}

export function ReasoningChain({ chain }: { chain: ReasoningChainType }) {
  const stages: Stage[] = [
    { label: "观察", text: chain.observed },
    { label: "组合\n暴露", text: chain.portfolio_exposure },
    { label: "推断", text: chain.inference },
    { label: "结论", text: chain.conclusion, emphasized: true },
  ];

  return (
    <section aria-labelledby="reasoning-heading" className="flex flex-col gap-[14px]">
      <span id="reasoning-heading" className="text-label">
        推理链
      </span>
      {stages.map((stage, idx) => (
        <div key={stage.label} className="flex flex-col gap-[14px]">
          <div className="flex items-start gap-[18px]">
            <span
              className="w-[92px] flex-none whitespace-pre-line font-sans text-[13px] font-medium leading-[1.35] text-ink-500"
            >
              {stage.label}
            </span>
            <span
              className={[
                "flex-1 font-sans text-[14px] leading-[1.45]",
                stage.emphasized ? "text-ink-900 font-medium" : "text-ink-700",
              ].join(" ")}
            >
              {stage.text}
            </span>
          </div>
          {idx < stages.length - 1 && (
            <div aria-hidden className="text-center font-mono text-[13px] leading-[1.2] text-ink-300">
              │<br />▼
            </div>
          )}
        </div>
      ))}
    </section>
  );
}
