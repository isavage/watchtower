import { useState } from "react";
import type { RangeKey } from "../lib/api";
import { useDetails, useSeries } from "../lib/hooks";
import { fmtBytes, fmtPct } from "../lib/format";
import { Layout } from "../components/Layout";
import { MetricCard } from "../components/MetricCard";
import { MetricChart } from "../components/MetricChart";
import { StatRow } from "../components/StatRow";
import { LoadingBlock, StatTile, TableCard, Td, Th, UsageBar } from "../components/ui";

export function MemoryPage() {
  const [range, setRange] = useState<RangeKey>("1h");
  const { data: d } = useDetails();
  const { points } = useSeries(range);

  if (!d) return <Layout title="Memory"><LoadingBlock /></Layout>;
  const m = d.memory;
  const realUsed = Math.max(m.used - m.buffers - m.cached, 0);

  const segs = [
    { label: "Used", value: realUsed, color: "#8b5cf6" },
    { label: "Buffers", value: m.buffers, color: "#0ea5e9" },
    { label: "Cached", value: m.cached, color: "#10b981" },
    { label: "Free", value: Math.max(m.free, 0), color: "#e2e8f0" },
  ];

  return (
    <Layout title="Memory" subtitle={`${fmtBytes(m.total)} physical · ${fmtBytes(m.available)} available`} range={range} onRange={setRange}>
      <div className="grid gap-5">
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <StatTile label="Used" value={fmtPct(m.pct)} sub={`${fmtBytes(m.used)} of ${fmtBytes(m.total)}`} />
          <StatTile label="Available" value={fmtBytes(m.available)} sub={`${fmtPct((m.available / m.total) * 100)} free`} />
          <StatTile
            label="Swap"
            value={m.swap_total ? fmtPct(m.swap_pct) : "—"}
            sub={m.swap_total ? `${fmtBytes(m.swap_used)} / ${fmtBytes(m.swap_total)}` : "not configured"}
          />
          <StatTile label="Shared" value={fmtBytes(m.shared)} sub={`active ${fmtBytes(m.active)}`} />
        </div>

        <MetricCard title="Memory usage" subtitle="% of physical memory in use" value={fmtPct(m.pct)}>
          <MetricChart
            data={points}
            unit="percent"
            domainMax={100}
            series={[{ key: "mem_pct", name: "Used", color: "#8b5cf6" }]}
          />
          <StatRow
            items={[
              { label: "Used", value: fmtBytes(m.used) },
              { label: "Cached", value: fmtBytes(m.cached) },
              { label: "Buffers", value: fmtBytes(m.buffers) },
            ]}
          />
        </MetricCard>

        <TableCard title="Breakdown" subtitle="live composition of physical memory">
          <div className="px-2">
            <div className="mb-4 flex h-3 w-full overflow-hidden rounded-full">
              {segs.map((s) => (
                <div
                  key={s.label}
                  className="h-full transition-[width] duration-500"
                  style={{ width: `${(s.value / m.total) * 100}%`, background: s.color }}
                  title={`${s.label}: ${fmtBytes(s.value)}`}
                />
              ))}
            </div>
            <div className="grid grid-cols-2 gap-x-8 gap-y-3 sm:grid-cols-4">
              {segs.map((s) => (
                <div key={s.label} className="flex items-center gap-2 text-sm">
                  <span className="h-2.5 w-2.5 rounded-full" style={{ background: s.color }} />
                  <span className="text-ink-500">{s.label}</span>
                  <span className="ml-auto font-mono tabular-nums text-ink-800">{fmtBytes(s.value)}</span>
                </div>
              ))}
            </div>
          </div>
        </TableCard>

        <TableCard title="Top processes by memory" subtitle={`of ${d.processes.count} processes · RSS`}>
          <table className="w-full">
            <thead>
              <tr>
                <Th>PID</Th>
                <Th>Process</Th>
                <Th>User</Th>
                <Th className="text-right">RSS</Th>
                <Th className="text-right">Mem %</Th>
                <Th className="hidden sm:table-cell">Share</Th>
              </tr>
            </thead>
            <tbody>
              {d.processes.top_mem.map((p) => (
                <tr key={p.pid} className="border-t border-ink-100">
                  <Td mono className="text-ink-400">{p.pid}</Td>
                  <Td className="font-medium text-ink-900">{p.name}</Td>
                  <Td className="text-ink-500">{p.user}</Td>
                  <Td mono className="text-right font-semibold text-ink-900">{fmtBytes(p.mem_rss)}</Td>
                  <Td mono className="text-right">{p.mem_pct.toFixed(1)}%</Td>
                  <Td className="hidden w-40 sm:table-cell">
                    <UsageBar pct={p.mem_pct} label="" color="#8b5cf6" />
                  </Td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableCard>
      </div>
    </Layout>
  );
}
