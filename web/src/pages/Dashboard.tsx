import { useState } from "react";
import type { RangeKey } from "../lib/api";
import { useSeries, useSummary } from "../lib/hooks";
import {
  fmtBytes,
  fmtNum,
  fmtPct,
  fmtRate,
  fmtUptime,
} from "../lib/format";
import { Layout } from "../components/Layout";
import { MetricCard } from "../components/MetricCard";
import { MetricChart } from "../components/MetricChart";
import { StatRow } from "../components/StatRow";

export function Dashboard() {
  const [range, setRange] = useState<RangeKey>("1h");
  const { latest } = useSummary();
  const { points, loading } = useSeries(range);

  const cores = latest?.cpu_count ?? undefined;

  return (
    <Layout
      title="Dashboard"
      subtitle={latest ? `${fmtUptime(latest.uptime)} uptime · ${latest.proc_count ?? "—"} processes` : "overview"}
      range={range}
      onRange={setRange}
    >
      {loading && points.length === 0 ? (
        <Empty />
      ) : (
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
            {/* CPU */}
            <MetricCard
              title="CPU"
              subtitle={cores ? `${cores} cores` : undefined}
              value={fmtPct(latest?.cpu_pct)}
            >
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

            {/* Memory */}
            <MetricCard
              title="Memory"
              subtitle={latest?.mem_total ? `${fmtBytes(latest.mem_total)} total` : undefined}
              value={fmtPct(latest?.mem_pct)}
            >
              <MetricChart
                data={points}
                unit="percent"
                domainMax={100}
                series={[{ key: "mem_pct", name: "Used", color: "#8b5cf6" }]}
              />
              <StatRow
                items={[
                  { label: "Used", value: fmtBytes(latest?.mem_used) },
                  { label: "Available", value: latest ? fmtBytes(Math.max((latest.mem_total ?? 0) - (latest.mem_used ?? 0), 0)) : "—" },
                  { label: "Swap", value: latest && latest.swap_total ? `${fmtBytes(latest.swap_used)} / ${fmtBytes(latest.swap_total)}` : "none" },
                ]}
              />
            </MetricCard>

            {/* Disk I/O */}
            <MetricCard
              title="Disk I/O"
              subtitle={latest?.disk_total ? `${fmtBytes(latest.disk_used)} / ${fmtBytes(latest.disk_total)} used` : undefined}
              value={fmtPct(latest?.disk_pct)}
            >
              <MetricChart
                data={points}
                unit="rate"
                series={[
                  { key: "disk_read", name: "Read", color: "#10b981" },
                  { key: "disk_write", name: "Write", color: "#f59e0b" },
                ]}
              />
              <StatRow
                items={[
                  { label: "Read", value: fmtRate(latest?.disk_read) },
                  { label: "Write", value: fmtRate(latest?.disk_write) },
                  { label: "Disk used", value: fmtPct(latest?.disk_pct) },
                ]}
              />
            </MetricCard>

            {/* Network */}
            <MetricCard
              title="Network"
              subtitle="throughput across all interfaces"
              value={
                latest ? (
                  <span className="flex gap-5">
                    <span className="flex items-center gap-1.5">
                      <Arrow dir="down" />
                      <span>{fmtRate(latest.net_recv)}</span>
                    </span>
                    <span className="flex items-center gap-1.5">
                      <Arrow dir="up" />
                      <span>{fmtRate(latest.net_sent)}</span>
                    </span>
                  </span>
                ) : (
                  "—"
                )
              }
            >
              <MetricChart
                data={points}
                unit="rate"
                series={[
                  { key: "net_recv", name: "Down", color: "#0ea5e9" },
                  { key: "net_sent", name: "Up", color: "#f43f5e" },
                ]}
              />
            </MetricCard>

            {/* System */}
            <div className="lg:col-span-2">
              <div className="card grid grid-cols-2 gap-px overflow-hidden bg-ink-200/60 sm:grid-cols-4">
                <MiniStat label="Uptime" value={fmtUptime(latest?.uptime)} />
                <MiniStat label="Processes" value={latest?.proc_count != null ? String(latest.proc_count) : "—"} />
                <MiniStat label="CPU cores" value={cores != null ? String(cores) : "—"} />
                <MiniStat label="Load / core" value={latest && cores && latest.load1 != null ? fmtNum(latest.load1 / cores, 2) : "—"} />
              </div>
            </div>
          </div>
      )}
    </Layout>
  );
}

function MiniStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-white px-5 py-4">
      <div className="text-xs text-ink-400">{label}</div>
      <div className="mt-1 font-mono text-lg font-semibold tabular-nums text-ink-900">{value}</div>
    </div>
  );
}

function Arrow({ dir }: { dir: "up" | "down" }) {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className={dir === "up" ? "text-rose-500" : "text-sky-500"}>
      {dir === "up" ? <path d="M12 19V5M5 12l7-7 7 7" /> : <path d="M12 5v14M19 12l-7 7-7-7" />}
    </svg>
  );
}

function Empty() {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-ink-300 bg-white/60 py-24 text-center">
      <div className="h-6 w-6 animate-spin rounded-full border-2 border-ink-300 border-t-ink-800" />
      <p className="mt-4 text-sm text-ink-500">Collecting metrics…</p>
      <p className="mt-1 text-xs text-ink-400">Charts appear once a few samples are in.</p>
    </div>
  );
}
