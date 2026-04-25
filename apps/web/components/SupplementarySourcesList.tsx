import type { SupplementarySource } from "@/lib/types";

export function SupplementarySourcesList({ sources }: { sources: SupplementarySource[] }) {
  if (sources.length === 0) return null;

  return (
    <section className="flex flex-col gap-2">
      <span className="text-label">补充来源</span>
      <ul className="flex flex-col gap-1">
        {sources.map((s) => (
          <li key={s.evidence_id} className="font-mono text-[11px] text-ink-500">
            <a
              href={s.source_link}
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-orange-600 hover:underline"
            >
              {s.label} ↗
            </a>
          </li>
        ))}
      </ul>
    </section>
  );
}
