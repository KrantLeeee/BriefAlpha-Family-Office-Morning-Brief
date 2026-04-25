interface Props {
  left: string;
  right: string;
  degraded: boolean;
  stale: boolean;
}

export function Footer({ left, right, degraded, stale }: Props) {
  const annotated = stale
    ? `${left} · ⚠ stale brief`
    : degraded
    ? `${left.replace("全部数据源正常", "数据源 degraded")}`
    : left;

  return (
    <footer className="border-t border-line bg-canvas">
      <div className="mx-auto flex h-[46px] max-w-[1440px] items-center justify-between px-8">
        <span className="font-mono text-[10px] text-ink-400">{annotated}</span>
        <span className="font-mono text-[11px] text-ink-400">{right}</span>
      </div>
    </footer>
  );
}
