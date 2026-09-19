import { useState } from "react";
import type { RangeKey } from "../lib/api";
import { useDetails, useSeries, useSummary } from "../lib/hooks";
import { fmtNum, fmtPct } from "../lib/format";
import { Layout } from "../components/Layout";
import { MetricCard } from "../components/MetricCard";
import { MetricChart } from "../components/MetricChart";
import { StatRow } from "../components/StatRow";
import { LoadingBlock, StatTile, TableCard, Td, Th } from "../components/ui";

const BREAKDOWN_COLORS: Record<string, string> = {
  user: "#0ea5e9",
  system: "#8b5cf6",
  iowait: "#f59e0b",
  irq: "#f43f5e",
  softirq: "#fb7185",
  steal: "#94a3b8",
  guest: "#64748b",
  guest_nice: "#cbd5e1",
};

export function CpuPage() {
  const [range, setRange] = useState<RangeKey>("1h");
  const { data: d } = useDetails();
  const { latest } = useSummary();
  const { points } = useSeries(range);

  if (!d) return <Layout title="CPU"><LoadingBlock /></Layout>;

  const cores = d.cpu.per_core.length;
  const breakdown = Object.entries(d.cpu.breakdown).filter(
    ([k, v]) => k !== "idle" && k !== "nice" && v > 0.05,
  );

  return (
    <Layout title="CPU" subtitle={`${cores} logical cores · load avg is per-core normalised`} range={range} onRange={setRange}>
      <div className="grid gap-5">
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <StatTile label="Usage" value={fmtPct(latest?.cpu_pct)} sub={`${cores} logical cores`} />
          <StatTile
            label="Load 1m"
            value={fmtNum(latest?.load1)}
            sub={latest && cores ? `${fmtNum((latest.load1 ?? 0) / cores, 2)} per core` : ""}
          />
          <StatTile
            label="Physical cores"
            value={d.cpu.count_physical ?? "—"}
            sub={d.cpu.freq?.current ? `${Math.round(d.cpu.freq.current)} MHz` : undefined}
          />
          <StatTile
            label="Processes"
            value={d.processes.count}
            sub={`${d.cpu.per_core.length} cores tracked`}
          />
        </div>

        <MetricCard title="CPU usage" subtitle="host aggregate, % of all cores" value={fmtPct(latest?.cpu_pct)}>
          <MetricChart
            data={points}
            unit="percent"
            domainMax={100}
            series={[{ key: "cpu_pct", name: "Usage", color: "#0ea5e9" }]}
          />
          <StatRow
            items={[
              { label: "Load 1m", value: fmtNum(latest?.load1) },
              { label: "Load 5m", value: fmtNum(latest?.load5) },
              { label: "Load 15m", value: fmtNum(latest?.load15) },
            ]}
          />
        </MetricCard>

        <TableCard
          title="Per-core utilisation"
          subtitle="live, refreshed every 2s"
          right={
            breakdown.length > 0 && (
              <div className="flex items-center gap-3 text-xs text-ink-500">
                {breakdown.map(([k]) => (
                  <span key={k} className="flex items-center gap-1.5">
                    <span className="h-2 w-2 rounded-full" style={{ background: BREAKDOWN_COLORS[k] ?? "#94a3b8" }} />
                    {k}
                  </span>
                ))}
              </div>
            )
          }
        >
          <div className="grid grid-cols-1 gap-x-8 gap-y-2 px-2 sm:grid-cols-2 lg:grid-cols-4">
            {d.cpu.per_core.map((c) => (
              <div key={c.core} className="flex items-center gap-2.5">
                <span className="w-8 shrink-0 font-mono text-[11px] tabular-nums text-ink-400">
                  {c.core}
                </span>
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-ink-100">
                  <div className="flex h-full">
                    {(["user", "system", "iowait"] as const).map((k) => {
                      const v = c[k] ?? 0;
                      if (v <= 0) return null;
                      return (
                        <div
                          key={k}
                          style={{ width: `${v}%`, background: BREAKDOWN_COLORS[k] }}
                          className="h-full transition-[width] duration-500"
                        />
                      );
                    })}
                  </div>
                </div>
                <span className="w-11 shrink-0 text-right font-mono text-[11px] tabular-nums text-ink-600">
                  {c.pct.toFixed(0)}%
                </span>
              </div>
            ))}
          </div>
        </TableCard>

        <TableCard title="Top processes by CPU" subtitle={`of ${d.processes.count} processes`}>
          <table className="w-full">
            <thead>
              <tr>
                <Th>PID</Th>
                <Th>Process</Th>
                <Th>User</Th>
                <Th className="text-right">CPU</Th>
                <Th className="text-right">Mem</Th>
                <Th className="text-right hidden sm:table-cell">Threads</Th>
                <Th className="hidden lg:table-cell">Command</Th>
              </tr>
            </thead>
            <tbody>
              {d.processes.top_cpu.map((p) => (
                <tr key={p.pid} className="border-t border-ink-100">
                  <Td mono className="text-ink-400">{p.pid}</Td>
                  <Td className="font-medium text-ink-900">{p.name}</Td>
                  <Td className="text-ink-500">{p.user}</Td>
                  <Td mono className="text-right font-semibold text-ink-900">{p.cpu_pct.toFixed(1)}%</Td>
                  <Td mono className="text-right">{p.mem_pct.toFixed(1)}%</Td>
                  <Td mono className="text-right hidden sm:table-cell">{p.threads}</Td>
                  <Td className="hidden max-w-[320px] truncate text-ink-400 lg:table-cell">{p.cmdline || "—"}</Td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableCard>
      </div>
    </Layout>
  );
}
