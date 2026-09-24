import { type ReactNode } from "react";

/** Thin horizontal usage meter with a label row. */
export function UsageBar({
  pct,
  label,
  right,
  color,
}: {
  pct: number | null | undefined;
  label: ReactNode;
  right?: ReactNode;
  color?: string;
}) {
  const v = pct == null ? 0 : Math.max(0, Math.min(100, pct));
  const tone = color ?? (v >= 90 ? "#ef4444" : v >= 75 ? "#f59e0b" : "#0ea5e9");
  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between gap-3 text-sm">
        <span className="min-w-0 truncate text-ink-700">{label}</span>
        <span className="shrink-0 font-mono text-xs tabular-nums text-ink-500">{right}</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-ink-100">
        <div
          className="h-full rounded-full transition-[width] duration-500"
          style={{ width: `${v}%`, backgroundColor: tone }}
        />
      </div>
    </div>
  );
}

/** Card with a title and a table inside. */
export function TableCard({
  title,
  subtitle,
  right,
  children,
}: {
  title: string;
  subtitle?: ReactNode;
  right?: ReactNode;
  children: ReactNode;
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
      <div className="-mx-2 flex-1 overflow-x-auto">{children}</div>
    </section>
  );
}

export type SortDirection = "asc" | "desc" | null;

export function SortIcon({ direction }: { direction: SortDirection }) {
  if (direction === "asc") {
    return (
      <svg className="inline-block h-3 w-3 shrink-0 text-ink-800" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M18 15l-6-6-6 6" />
      </svg>
    );
  }
  if (direction === "desc") {
    return (
      <svg className="inline-block h-3 w-3 shrink-0 text-ink-800" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M6 9l6 6 6-6" />
      </svg>
    );
  }
  return (
    <svg className="inline-block h-3 w-3 shrink-0 text-ink-300 opacity-40 group-hover:opacity-100 transition-opacity" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M7 15l5 5 5-5" />
      <path d="M7 9l5-5 5 5" />
    </svg>
  );
}

export function Th({
  children,
  className = "",
  sortKey,
  currentSortKey,
  sortDirection,
  onSort,
}: {
  children?: ReactNode;
  className?: string;
  sortKey?: string;
  currentSortKey?: string | null;
  sortDirection?: SortDirection;
  onSort?: (key: string) => void;
}) {
  if (!sortKey || !onSort) {
    return (
      <th
        className={`whitespace-nowrap px-2 py-1.5 text-left text-[11px] font-medium uppercase tracking-wide text-ink-400 ${className}`}
      >
        {children}
      </th>
    );
  }

  const isSorted = currentSortKey === sortKey;
  const dir = isSorted ? sortDirection ?? null : null;
  const isRight = className.includes("text-right");

  return (
    <th
      onClick={() => onSort(sortKey)}
      className={`group cursor-pointer select-none whitespace-nowrap px-2 py-1.5 text-left text-[11px] font-medium uppercase tracking-wide transition-colors hover:text-ink-800 ${
        isSorted ? "text-ink-900 font-semibold" : "text-ink-400"
      } ${className}`}
    >
      <span className={`inline-flex items-center gap-1 ${isRight ? "justify-end w-full" : ""}`}>
        {children}
        <SortIcon direction={dir} />
      </span>
    </th>
  );
}

export function Td({
  children,
  className = "",
  mono,
}: {
  children?: ReactNode;
  className?: string;
  mono?: boolean;
}) {
  return (
    <td
      className={`whitespace-nowrap px-2 py-1.5 text-[13px] text-ink-700 ${
        mono ? "font-mono tabular-nums" : ""
      } ${className}`}
    >
      {children}
    </td>
  );
}

export function StatTile({ label, value, sub }: { label: string; value: ReactNode; sub?: ReactNode }) {
  return (
    <div className="card px-5 py-4">
      <div className="text-xs text-ink-400">{label}</div>
      <div className="mt-1 font-mono text-xl font-semibold tabular-nums text-ink-900">{value}</div>
      {sub && <div className="mt-0.5 text-xs text-ink-400">{sub}</div>}
    </div>
  );
}

export function Spinner() {
  return <div className="h-6 w-6 animate-spin rounded-full border-2 border-ink-300 border-t-ink-800" />;
}

export function LoadingBlock() {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-ink-300 bg-white/60 py-24">
      <Spinner />
      <p className="mt-4 text-sm text-ink-500">Loading…</p>
    </div>
  );
}
