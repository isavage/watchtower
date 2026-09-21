import { useMemo } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { MetricPoint } from "../lib/api";
import { fmtBytes, fmtClock, fmtClockWithDate, fmtClockWithHours } from "../lib/format";

interface Series {
  key: keyof MetricPoint;
  name: string;
  color: string;
}

interface Props {
  data: MetricPoint[];
  series: Series[];
  unit?: "percent" | "bytes" | "rate" | "number";
  domainMax?: number | "auto" | "dataMax";
  wide?: boolean;
}

function formatValue(v: number | null | undefined, unit?: Props["unit"]): string {
  if (v == null) return "—";
  switch (unit) {
    case "percent":
      return `${v.toFixed(1)}%`;
    case "rate":
      return `${(v / 1024 / 1024).toFixed(2)} MB/s`;
    case "bytes":
      return `${(v / 1024 / 1024 / 1024).toFixed(2)} GB`;
    default:
      return v.toFixed(2);
  }
}

function ChartTooltip({ active, payload, label, unit }: any) {
  if (!active || !payload || !payload.length) return null;
  return (
    <div className="rounded-xl border border-ink-200 bg-white/95 px-3 py-2 text-xs shadow-lg backdrop-blur">
      <div className="mb-1 font-medium text-ink-500">{fmtClockWithHours(label)}</div>
      {payload.map((p: any) => (
        <div key={p.dataKey} className="flex items-center gap-2 text-ink-800">
          <span className="inline-block h-2 w-2 rounded-full" style={{ background: p.color }} />
          <span className="text-ink-500">{p.name}</span>
          <span className="ml-auto font-mono tabular-nums">{formatValue(p.value, unit)}</span>
        </div>
      ))}
    </div>
  );
}

export function MetricChart({ data, series, unit, domainMax = "auto", wide }: Props) {
  const isMultiDay = useMemo(() => {
    if (!data || data.length < 2) return false;
    const first = data[0]?.ts;
    const last = data[data.length - 1]?.ts;
    if (typeof first !== "number" || typeof last !== "number") return false;
    return Math.abs(last - first) > 86400;
  }, [data]);

  const gradient = (id: string, color: string) => (
    <linearGradient key={id} id={id} x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stopColor={color} stopOpacity={0.28} />
      <stop offset="100%" stopColor={color} stopOpacity={0.02} />
    </linearGradient>
  );

  return (
    <ResponsiveContainer width="100%" height={wide ? 260 : 200}>
      <AreaChart data={data} margin={{ top: 8, right: 8, left: 4, bottom: 0 }}>
        <defs>
          {series.map((s) => gradient(`grad-${String(s.key)}`, s.color))}
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#eef2f6" vertical={false} />
        <XAxis
          dataKey="ts"
          tickFormatter={(t) => (isMultiDay ? fmtClockWithDate(t) : fmtClock(t))}
          minTickGap={isMultiDay ? 50 : 40}
          tick={{ fontSize: 11, fill: "#94a3b8" }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          domain={[0, domainMax]}
          width={52}
          tick={{ fontSize: 11, fill: "#94a3b8" }}
          axisLine={false}
          tickLine={false}
          tickFormatter={(v) =>
            unit === "percent"
              ? `${v}%`
              : unit === "rate" || unit === "bytes"
                ? fmtBytes(v, 0)
                : `${v}`
          }
        />
        <Tooltip content={<ChartTooltip unit={unit} />} />
        {series.map((s) => (
          <Area
            key={String(s.key)}
            type="monotone"
            dataKey={s.key as string}
            name={s.name}
            stroke={s.color}
            strokeWidth={2}
            fill={`url(#grad-${String(s.key)})`}
            isAnimationActive={false}
            connectNulls
            dot={false}
            activeDot={{ r: 3, strokeWidth: 0 }}
          />
        ))}
      </AreaChart>
    </ResponsiveContainer>
  );
}
