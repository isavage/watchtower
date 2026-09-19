import { Ranges } from "../lib/ranges";
import type { RangeKey } from "../lib/api";

export function TimeRangeSelector({
  value,
  onChange,
}: {
  value: RangeKey;
  onChange: (r: RangeKey) => void;
}) {
  return (
    <div className="inline-flex items-center gap-1 rounded-xl border border-ink-200/70 bg-ink-100/60 p-1">
      {Ranges.map((r) => (
        <button
          key={r.key}
          onClick={() => onChange(r.key)}
          className={`seg-btn ${value === r.key ? "seg-btn-active" : ""}`}
        >
          {r.label}
        </button>
      ))}
    </div>
  );
}
