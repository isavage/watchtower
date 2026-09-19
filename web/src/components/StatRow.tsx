import type { ReactNode } from "react";

export function StatRow({ items }: { items: { label: string; value: ReactNode }[] }) {
  return (
    <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-2 sm:grid-cols-3">
      {items.map((it) => (
        <div key={it.label} className="flex items-baseline justify-between gap-2">
          <dt className="text-xs text-ink-400">{it.label}</dt>
          <dd className="font-mono text-xs font-medium tabular-nums text-ink-700">{it.value}</dd>
        </div>
      ))}
    </dl>
  );
}
