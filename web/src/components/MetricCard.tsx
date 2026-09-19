import type { ReactNode } from "react";

export function MetricCard({
  title,
  subtitle,
  value,
  children,
  right,
}: {
  title: string;
  subtitle?: ReactNode;
  value?: ReactNode;
  children?: ReactNode;
  right?: ReactNode;
}) {
  return (
    <section className="card flex flex-col p-5">
      <header className="mb-3 flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-ink-900">{title}</h3>
          {subtitle && <p className="mt-0.5 text-xs text-ink-400">{subtitle}</p>}
        </div>
        {right}
      </header>
      {value != null && (
        <div className="mb-3 font-mono text-2xl font-semibold tabular-nums text-ink-900">
          {value}
        </div>
      )}
      <div className="mt-auto">{children}</div>
    </section>
  );
}
