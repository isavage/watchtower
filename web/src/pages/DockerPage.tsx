import { useMemo, useState } from "react";
import { useDocker, useSummary } from "../lib/hooks";
import { fmtBytes, fmtDuration, fmtNum, fmtUptime } from "../lib/format";
import { Layout } from "../components/Layout";
import { LoadingBlock, StatTile, TableCard, Td, Th, UsageBar } from "../components/ui";

function PortBadges({ ports }: { ports: { PublicPort?: number; PrivatePort: number; Type: string }[] }) {
  if (!ports.length) return <span className="text-ink-400">—</span>;
  return <div className="flex max-w-[220px] flex-wrap gap-1">{ports.map((port, index) => {
    const host = port.PublicPort != null;
    return <span key={`${port.PrivatePort}-${port.PublicPort ?? "exposed"}-${index}`} title={host ? "Published host port" : "Container-only exposed port"} className={`inline-flex items-center rounded-full px-2 py-0.5 font-mono text-[11px] font-medium ${host ? "bg-sky-50 text-sky-700 ring-1 ring-sky-200" : "bg-amber-50 text-amber-700 ring-1 ring-amber-200"}`}>
      {host ? `${port.PublicPort}:` : ""}{port.PrivatePort}/{port.Type}
    </span>;
  })}</div>;
}
export function DockerPage() {
  const { data, error } = useDocker();
  const { latest } = useSummary();
  const [filter, setFilter] = useState("");

  const rows = useMemo(() => {
    const list = data?.containers ?? [];
    const q = filter.trim().toLowerCase();
    if (!q) return list;
    return list.filter((c) => c.name.toLowerCase().includes(q) || c.image.toLowerCase().includes(q));
  }, [data, filter]);

  return (
    <Layout
      title="Docker"
      subtitle="Docker workloads on this host, live from the Engine API"
      actions={
        data?.available ? (
          <input
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Filter by name or image…"
            className="w-56 rounded-xl border border-ink-200 bg-white px-3 py-1.5 text-sm text-ink-800 placeholder:text-ink-400 focus:border-ink-400 focus:outline-none"
          />
        ) : undefined
      }
    >
      {error && !data ? (
        <div className="card p-6 text-sm text-ink-500">{error}</div>
      ) : !data ? (
        <LoadingBlock />
      ) : !data.available ? (
        <div className="card flex flex-col items-center gap-2 p-12 text-center">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-ink-300" strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="13" width="5" height="5" rx="1" />
            <rect x="9.5" y="13" width="5" height="5" rx="1" />
            <rect x="16" y="13" width="5" height="5" rx="1" />
            <rect x="9.5" y="7" width="5" height="5" rx="1" />
            <path d="M3 3l18 18" />
          </svg>
          <p className="text-sm font-medium text-ink-700">Docker socket not available</p>
          <p className="max-w-md text-xs text-ink-400">
            Mount <code className="rounded bg-ink-100 px-1 py-0.5 font-mono">/var/run/docker.sock</code> into
            the watchtower container (already present in docker-compose.yml) and redeploy.
          </p>
        </div>
      ) : (
        <div className="grid gap-5">
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <StatTile label="Running" value={data.count ?? 0} sub="containers" />
            <StatTile
              label="Docker CPU"
              value={`${fmtNum(data.cpu_total ?? 0, 1)}%`}
              sub={latest ? `host at ${fmtNum(latest.cpu_pct ?? 0, 0)}%` : undefined}
            />
            <StatTile label="Docker memory" value={fmtBytes(data.memory?.total ?? 0)} sub="across containers" />
            <StatTile label="Host uptime" value={fmtUptime(latest?.uptime)} />
          </div>

          <TableCard title="Containers" subtitle={`sorted by CPU · ${rows.length} shown`}>
            <div className="mb-3 flex flex-wrap gap-2 px-2 text-xs text-ink-500"><span className="inline-flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-sky-500" />host published</span><span className="inline-flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-amber-500" />container exposed</span></div>
            <table className="w-full">
              <thead>
                <tr>
                  <Th>Container</Th>
                  <Th className="hidden sm:table-cell">Ports</Th>
                  <Th>Status</Th>
                  <Th className="w-36">CPU</Th>
                  <Th className="w-36">Memory</Th>
                  <Th className="text-right hidden md:table-cell">Net ↓ / ↑ total</Th>
                  <Th className="text-right hidden lg:table-cell">Block I/O</Th>
                  <Th className="text-right hidden sm:table-cell">Up</Th>
                </tr>
              </thead>
              <tbody>
                {rows.map((c) => (
                  <tr key={c.id} className="border-t border-ink-100 align-middle">
                    <Td>
                      <div className="font-medium text-ink-900">{c.name}</div>
                      <div className="font-mono text-[10px] text-ink-400">{c.id}</div>
                    </Td>
                    <Td className="hidden text-ink-500 sm:table-cell"><PortBadges ports={c.ports ?? []} /></Td>
                    <Td>
                      <span
                        className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium ${
                          c.state === "running" ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"
                        }`}
                      >
                        <span className={`h-1.5 w-1.5 rounded-full ${c.state === "running" ? "bg-emerald-500" : "bg-amber-500"}`} />
                        {c.status || c.state}
                      </span>
                    </Td>
                    <Td>
                      <UsageBar pct={c.cpu_pct} label="" color="#0ea5e9" right={c.cpu_pct != null ? `${c.cpu_pct.toFixed(1)}%` : "—"} />
                    </Td>
                    <Td>
                      <UsageBar
                        pct={c.mem_pct}
                        label=""
                        color="#8b5cf6"
                        right={c.mem_usage != null ? `${fmtBytes(c.mem_usage)}${c.mem_pct != null ? ` · ${c.mem_pct.toFixed(0)}%` : ""}` : "—"}
                      />
                    </Td>
                    <Td mono className="text-right hidden text-ink-500 md:table-cell">
                      {c.net_rx != null ? `${fmtBytes(c.net_rx)} / ${fmtBytes(c.net_tx ?? 0)}` : "—"}
                    </Td>
                    <Td mono className="text-right hidden text-ink-500 lg:table-cell">
                      {c.blkio != null ? fmtBytes(c.blkio) : "—"}
                    </Td>
                    <Td mono className="text-right hidden text-ink-500 sm:table-cell">
                      {c.age != null ? fmtDuration(c.age) : "—"}
                    </Td>
                  </tr>
                ))}
                {rows.length === 0 && (
                  <tr>
                    <Td className="text-ink-400">No containers match.</Td>
                  </tr>
                )}
              </tbody>
            </table>
          </TableCard>
        </div>
      )}
    </Layout>
  );
}
