import { useMemo, useState } from "react";
import type { RangeKey } from "../lib/api";
import { useDetails, useSeries, useSortable } from "../lib/hooks";
import { fmtBytes, fmtRate } from "../lib/format";
import { Layout } from "../components/Layout";
import { MetricCard } from "../components/MetricCard";
import { MetricChart } from "../components/MetricChart";
import { LoadingBlock, StatTile, TableCard, Td, Th } from "../components/ui";

function Arrow({ dir }: { dir: "up" | "down" }) {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={dir === "up" ? "text-rose-500" : "text-sky-500"}
    >
      {dir === "up" ? <path d="M12 19V5M5 12l7-7 7 7" /> : <path d="M12 5v14M19 12l-7 7-7-7" />}
    </svg>
  );
}

export function NetworkPage() {
  const [range, setRange] = useState<RangeKey>("1h");
  const { data: d } = useDetails();
  const { points } = useSeries(range);

  const nics = useMemo(() => d?.network?.interfaces ?? [], [d]);

  const addrsByIface = useMemo(() => {
    const map = new Map<string, string[]>();
    if (!d?.addresses) return map;
    for (const a of d.addresses) {
      const list = map.get(a.iface) ?? [];
      list.push(a.address);
      map.set(a.iface, list);
    }
    return map;
  }, [d]);

  const sortGetters = useMemo(() => ({
    name: (n: any) => n.name,
    status: (n: any) => (n.up ? 1 : 0),
    addresses: (n: any) => (addrsByIface.get(n.name) ?? []).join(" "),
    link: (n: any) => n.speed_mbps ?? 0,
    recv_rate: (n: any) => n.recv_rate ?? 0,
    sent_rate: (n: any) => n.sent_rate ?? 0,
    err_drop: (n: any) => (n.packets_err ?? 0) + (n.packets_drop ?? 0),
  }), [addrsByIface]);

  const { items: sortedNics, sortKey, sortDirection, toggleSort } = useSortable(
    nics,
    "name",
    "asc",
    sortGetters
  );

  if (!d) return <Layout title="Network"><LoadingBlock /></Layout>;

  const total = nics.reduce(
    (a, n) => ({ rx: a.rx + (n.recv_rate ?? 0), tx: a.tx + (n.sent_rate ?? 0) }),
    { rx: 0, tx: 0 },
  );

  return (
    <Layout title="Network" subtitle={`${nics.length} interfaces · aggregate throughput`} range={range} onRange={setRange}>
      <div className="grid gap-5">
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <StatTile label="Down" value={fmtRate(total.rx)} sub="now, all interfaces" />
          <StatTile label="Up" value={fmtRate(total.tx)} sub="now, all interfaces" />
          <StatTile
            label="Total received"
            value={fmtBytes(nics.reduce((s, n) => s + n.recv_total, 0))}
            sub="since boot"
          />
          <StatTile
            label="Total sent"
            value={fmtBytes(nics.reduce((s, n) => s + n.sent_total, 0))}
            sub="since boot"
          />
        </div>

        <MetricCard
          title="Throughput"
          subtitle="host-wide, bytes per second"
          value={
            <span className="flex gap-5 text-xl">
              <span className="flex items-center gap-1.5"><Arrow dir="down" />{fmtRate(total.rx)}</span>
              <span className="flex items-center gap-1.5"><Arrow dir="up" />{fmtRate(total.tx)}</span>
            </span>
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

        <TableCard title="Interfaces" subtitle="live rates refreshed every 2s">
          <table className="w-full">
            <thead>
              <tr>
                <Th sortKey="name" currentSortKey={sortKey} sortDirection={sortDirection} onSort={toggleSort}>Interface</Th>
                <Th sortKey="status" currentSortKey={sortKey} sortDirection={sortDirection} onSort={toggleSort}>Status</Th>
                <Th sortKey="addresses" currentSortKey={sortKey} sortDirection={sortDirection} onSort={toggleSort} className="hidden sm:table-cell">Addresses</Th>
                <Th sortKey="link" currentSortKey={sortKey} sortDirection={sortDirection} onSort={toggleSort} className="hidden md:table-cell">Link</Th>
                <Th sortKey="recv_rate" currentSortKey={sortKey} sortDirection={sortDirection} onSort={toggleSort} className="text-right">Down</Th>
                <Th sortKey="sent_rate" currentSortKey={sortKey} sortDirection={sortDirection} onSort={toggleSort} className="text-right">Up</Th>
                <Th sortKey="err_drop" currentSortKey={sortKey} sortDirection={sortDirection} onSort={toggleSort} className="text-right hidden sm:table-cell">Err / Drop</Th>
              </tr>
            </thead>
            <tbody>
              {sortedNics.map((n) => (
                <tr key={n.name} className="border-t border-ink-100">
                  <Td className="font-medium text-ink-900">{n.name}</Td>
                  <Td>
                    <span
                      className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium ${
                        n.up ? "bg-emerald-50 text-emerald-700" : "bg-ink-100 text-ink-500"
                      }`}
                    >
                      <span className={`h-1.5 w-1.5 rounded-full ${n.up ? "bg-emerald-500" : "bg-ink-400"}`} />
                      {n.up ? "up" : "down"}
                    </span>
                  </Td>
                  <Td mono className="hidden text-xs text-ink-500 sm:table-cell">
                    {(addrsByIface.get(n.name) ?? []).slice(0, 2).join("  ") || "—"}
                  </Td>
                  <Td className="hidden text-ink-500 md:table-cell">
                    {n.speed_mbps ? `${n.speed_mbps >= 1000 ? `${n.speed_mbps / 1000} Gbps` : `${n.speed_mbps} Mbps`}` : "—"}
                    {n.mtu ? ` · mtu ${n.mtu}` : ""}
                  </Td>
                  <Td mono className="text-right text-sky-600">{n.recv_rate != null ? fmtRate(n.recv_rate) : "—"}</Td>
                  <Td mono className="text-right text-rose-600">{n.sent_rate != null ? fmtRate(n.sent_rate) : "—"}</Td>
                  <Td mono className={`text-right hidden sm:table-cell ${n.packets_err + n.packets_drop ? "text-amber-600" : "text-ink-400"}`}>
                    {n.packets_err} / {n.packets_drop}
                  </Td>
                </tr>
              ))}
              {sortedNics.length === 0 && (
                <tr><Td className="text-ink-400">No non-loopback interfaces found.</Td></tr>
              )}
            </tbody>
          </table>
        </TableCard>
      </div>
    </Layout>
  );
}
