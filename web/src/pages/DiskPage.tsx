import { useState } from "react";
import type { RangeKey } from "../lib/api";
import { useDetails, useSeries } from "../lib/hooks";
import { fmtBytes, fmtNum, fmtPct, fmtRate } from "../lib/format";
import { Layout } from "../components/Layout";
import { MetricCard } from "../components/MetricCard";
import { MetricChart } from "../components/MetricChart";
import { LoadingBlock, StatTile, TableCard, Td, Th, UsageBar } from "../components/ui";

export function DiskPage() {
  const [range, setRange] = useState<RangeKey>("1h");
  const { data: d } = useDetails();
  const { points } = useSeries(range);

  if (!d) return <Layout title="Disk"><LoadingBlock /></Layout>;

  const root = d.partitions.find((p) => p.mountpoint === "/") ?? d.partitions[0];
  const ioTotal = d.disk_io.devices.reduce(
    (acc, x) => ({
      read: acc.read + (x.read_rate ?? 0),
      write: acc.write + (x.write_rate ?? 0),
      ops: acc.ops + (x.ops ?? 0),
    }),
    { read: 0, write: 0, ops: 0 },
  );

  return (
    <Layout
      title="Disk"
      subtitle={root ? `${fmtBytes(root.used)} used of ${fmtBytes(root.total)} on ${root.mountpoint}` : undefined}
      range={range}
      onRange={setRange}
    >
      <div className="grid gap-5">
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <StatTile label="Root usage" value={fmtPct(root?.pct)} sub={root ? `${fmtBytes(root.free)} free` : "—"} />
          <StatTile label="Read rate" value={fmtRate(ioTotal.read)} sub="all devices" />
          <StatTile label="Write rate" value={fmtRate(ioTotal.write)} sub="all devices" />
          <StatTile label="IOPS" value={fmtNum(ioTotal.ops, 0)} sub="read + write ops/s" />
        </div>

        <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
          <MetricCard title="Disk I/O" subtitle="bytes per second, all devices" value={
            <span className="flex gap-5 text-xl">
              <span>R {fmtRate(ioTotal.read)}</span>
              <span>W {fmtRate(ioTotal.write)}</span>
            </span>
          }>
            <MetricChart
              data={points}
              unit="rate"
              series={[
                { key: "disk_read", name: "Read", color: "#10b981" },
                { key: "disk_write", name: "Write", color: "#f59e0b" },
              ]}
            />
          </MetricCard>

          <TableCard title="Partitions" subtitle="mounted filesystems">
            <div className="space-y-4 px-2">
              {d.partitions.map((p) => (
                <UsageBar
                  key={p.mountpoint}
                  pct={p.pct}
                  label={<span className="font-medium text-ink-800">{p.mountpoint}</span>}
                  right={
                    <span>
                      {fmtPct(p.pct)} · {fmtBytes(p.used)}/{fmtBytes(p.total)} · {p.fstype}
                    </span>
                  }
                />
              ))}
              {d.partitions.length === 0 && <p className="px-2 text-sm text-ink-400">No mounted filesystems found.</p>}
            </div>
          </TableCard>
        </div>

        <TableCard title="Block devices" subtitle="live I/O counters (from /proc/diskstats)">
          <table className="w-full">
            <thead>
              <tr>
                <Th>Device</Th>
                <Th className="text-right">Read/s</Th>
                <Th className="text-right">Write/s</Th>
                <Th className="text-right">IOPS</Th>
                <Th className="text-right hidden sm:table-cell">Read total</Th>
                <Th className="text-right hidden sm:table-cell">Write total</Th>
              </tr>
            </thead>
            <tbody>
              {d.disk_io.devices.map((x) => (
                <tr key={x.name} className="border-t border-ink-100">
                  <Td className="font-medium text-ink-900">{x.name}</Td>
                  <Td mono className="text-right">{x.read_rate != null ? fmtRate(x.read_rate) : "—"}</Td>
                  <Td mono className="text-right">{x.write_rate != null ? fmtRate(x.write_rate) : "—"}</Td>
                  <Td mono className="text-right">{x.ops != null ? fmtNum(x.ops, 0) : "—"}</Td>
                  <Td mono className="text-right hidden text-ink-500 sm:table-cell">{fmtBytes(x.read_total)}</Td>
                  <Td mono className="text-right hidden text-ink-500 sm:table-cell">{fmtBytes(x.write_total)}</Td>
                </tr>
              ))}
              {d.disk_io.devices.length === 0 && (
                <tr>
                  <Td className="text-ink-400" >No disk I/O counters available.</Td>
                </tr>
              )}
            </tbody>
          </table>
        </TableCard>
      </div>
    </Layout>
  );
}
